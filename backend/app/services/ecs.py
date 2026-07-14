"""Launch long-running application jobs as ECS/Fargate tasks."""

from __future__ import annotations

import json
import socket
from threading import Thread, get_ident
from typing import Any, Callable

from backend.app.config import ConfigurationError, Settings, get_settings
from backend.app.observability import log_health_event
from backend.app.repository import S3Repository, iso_now


class TaskLaunchError(RuntimeError):
    pass


class EcsTaskLauncher:
    def __init__(self, settings: Settings | None = None, *, client: Any | None = None) -> None:
        self.settings = settings or get_settings()
        if client is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover - dependency guard
                raise ConfigurationError("boto3 is required for ECS task launching.") from exc
            client = boto3.client("ecs", region_name=self.settings.aws_region)
        self.client = client

    def start(self, job: dict[str, Any]) -> str:
        self.settings.require_ecs()
        payload = {
            "job_id": job["job_id"],
            "operation": job["operation"],
            "owner": job["owner_name"],
            "company_id": job.get("company_id"),
            "source_id": job.get("source_id"),
            "run_id": job.get("run_id"),
            "options": job.get("options") or {},
            "correlation_id": job["correlation_id"],
        }
        container = {
            "name": self.settings.ecs_container_name or "worker",
            "environment": [
                {"name": "SENTINEL_JOB_ID", "value": str(job["job_id"])},
                {"name": "SENTINEL_JOB_PAYLOAD", "value": json.dumps(payload, separators=(",", ":"))},
            ],
        }
        request: dict[str, Any] = {
            "cluster": self.settings.ecs_cluster,
            "taskDefinition": self.settings.ecs_task_definition,
            "launchType": self.settings.ecs_launch_type,
            "overrides": {"containerOverrides": [container]},
            "startedBy": f"sentinel-{job['job_id']}",
            "tags": [
                {"key": "application", "value": "sentinel-actalyst"},
                {"key": "job_id", "value": str(job["job_id"])},
                {"key": "correlation_id", "value": str(job["correlation_id"])},
            ],
        }
        if self.settings.ecs_network_configuration:
            request["networkConfiguration"] = self.settings.ecs_network_configuration
        try:
            response = self.client.run_task(**request)
        except Exception as exc:
            raise TaskLaunchError(f"ECS task launch failed: {exc}") from exc
        failures = response.get("failures") or []
        tasks = response.get("tasks") or []
        if failures or not tasks:
            reason = str((failures[0] if failures else {}).get("reason") or "ECS returned no task")
            raise TaskLaunchError(f"ECS task launch failed: {reason}")
        task_arn = tasks[0].get("taskArn")
        if not task_arn:
            raise TaskLaunchError("ECS task launch returned no task ARN.")
        return str(task_arn)


class LocalJobRunner:
    """Development-only asynchronous job runner hosted by the API process."""

    def __init__(
        self,
        repository: S3Repository,
        *,
        execute: Callable[[S3Repository, dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.repository = repository
        self._execute = execute

    def start(self, job: dict[str, Any]) -> None:
        thread = Thread(
            target=self._run,
            args=(str(job["job_id"]), str(job["owner_name"])),
            name=f"sentinel-local-job-{str(job['job_id'])[:8]}",
            daemon=True,
        )
        thread.start()

    def _run(self, job_id: str, owner: str) -> None:
        try:
            claimed = self.repository.claim_job(
                job_id,
                owner,
                f"local-{socket.gethostname()}-{get_ident()}",
            )
            if claimed is None:
                return
            if self._execute is None:
                from backend.app.services.monitor_service import execute_job

                self._execute = execute_job
            self._execute(self.repository, claimed)
        except Exception as exc:
            try:
                current = self.repository.get_job(job_id, owner)
                if current.get("status") not in {"succeeded", "partially_succeeded", "failed", "cancelled"}:
                    self.repository.update_job(
                        job_id,
                        owner,
                        status="failed",
                        completed_at=iso_now(),
                        error={"message": str(exc), "safe_message": "Local monitoring task failed."},
                    )
            finally:
                log_health_event(
                    event_type="local_task",
                    service="backend",
                    action="execute",
                    status="error",
                    correlation_id=None,
                    metadata={"job_id": job_id, "error_type": type(exc).__name__},
                )


class JobDispatcher:
    """Creates an application job, then starts exactly one Fargate task for it."""

    def __init__(
        self,
        repository: S3Repository,
        launcher: EcsTaskLauncher | None = None,
        *,
        settings: Settings | None = None,
        local_runner: LocalJobRunner | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings or get_settings()
        self.launcher = launcher
        self.local_runner = local_runner

    def _dispatch_local(self, job: dict[str, Any]) -> dict[str, Any]:
        owner = str(job["owner_name"])
        job_id = str(job["job_id"])
        updated = self.repository.update_job(
            job_id,
            owner,
            status="starting",
            ecs_task_arn=f"local://{job_id}",
        )
        try:
            (self.local_runner or LocalJobRunner(self.repository)).start(updated)
        except Exception as exc:
            self.repository.update_job(
                job_id,
                owner,
                status="failed",
                completed_at=iso_now(),
                error={"message": str(exc), "safe_message": "Local monitoring task could not be started."},
            )
            raise TaskLaunchError(str(exc)) from exc
        return updated

    def dispatch(self, job: dict[str, Any]) -> dict[str, Any]:
        backend = self.settings.require_task_execution_backend()
        if backend == "local":
            return self._dispatch_local(job)

        owner = str(job["owner_name"])
        job_id = str(job["job_id"])
        try:
            self.repository.update_job(job_id, owner, status="starting")
            task_arn = (self.launcher or EcsTaskLauncher(self.settings)).start(job)
            updated = self.repository.update_job(job_id, owner, ecs_task_arn=task_arn, status="starting")
        except Exception as exc:
            self.repository.update_job(
                job_id,
                owner,
                status="failed",
                completed_at=iso_now(),
                error={"message": str(exc), "safe_message": "Task could not be started."},
            )
            log_health_event(
                event_type="ecs_task",
                service="api",
                action="launch",
                status="error",
                correlation_id=job.get("correlation_id"),
                metadata={"job_id": job_id, "operation": job["operation"], "error": str(exc)},
            )
            raise TaskLaunchError(str(exc)) from exc
        log_health_event(
            event_type="ecs_task",
            service="api",
            action="launch",
            status="ok",
            correlation_id=job.get("correlation_id"),
            metadata={"job_id": job_id, "operation": job["operation"], "task_arn": task_arn},
        )
        return updated
