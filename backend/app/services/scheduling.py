"""EventBridge-triggered due-monitor selection.

The EventBridge target runs this code in a short Fargate task.  It only selects
enabled monitors whose cadence is due; each selected monitor becomes a normal,
idempotent application job and Fargate task.
"""

from __future__ import annotations

from typing import Any

from backend.app.repository import S3Repository, iso_now
from backend.app.services.ecs import JobDispatcher, TaskLaunchError


def dispatch_due_monitors(repository: S3Repository, dispatcher: JobDispatcher) -> dict[str, Any]:
    queued: list[int] = []
    failures: list[dict[str, str | int]] = []
    for source in repository.due_sources():
        owner = str(source["owner_name"])
        job = repository.create_job(
            owner,
            operation="monitor",
            company_id=int(source["company_id"]),
            source_id=int(source["id"]),
            options={"scheduled": True},
        )
        run = repository.create_run(owner, source, "monitor", str(job["job_id"]))
        repository.update_job(str(job["job_id"]), owner, run_id=int(run["id"]))
        try:
            dispatcher.dispatch(repository.get_job(str(job["job_id"]), owner))
            repository.update_source(int(source["id"]), owner, last_checked_at=iso_now())
            queued.append(int(source["id"]))
        except TaskLaunchError as exc:
            failures.append({"source_id": int(source["id"]), "error": str(exc)})
    return {"queued_source_ids": queued, "failures": failures, "executed_at": iso_now()}
