"""ECS task entry point. It consumes application jobs, not Celery messages."""

from __future__ import annotations

import os
import socket

from backend.app.auth import bootstrap_accounts
from backend.app.config import get_settings
from backend.app.repository import get_repository
from backend.app.services.monitor_service import execute_job
from backend.app.services.scheduling import dispatch_due_monitors
from backend.app.services.ecs import JobDispatcher


def run_job(job_id: str) -> dict:
    settings = get_settings()
    settings.require_storage()
    repository = get_repository()
    bootstrap_accounts(repository)
    job = repository.get_job(job_id)
    claimed = repository.claim_job(job_id, str(job["owner_name"]), socket.gethostname())
    if claimed is None:
        return {"status": "skipped", "reason": "job already claimed or complete", "job_id": job_id}
    return execute_job(repository, claimed)


def main() -> None:
    job_id = os.getenv("SENTINEL_JOB_ID")
    if job_id:
        run_job(job_id)
        return
    # EventBridge runs a task without a job ID for cadence selection.
    repository = get_repository()
    dispatch_due_monitors(repository, JobDispatcher(repository))


if __name__ == "__main__":
    main()
