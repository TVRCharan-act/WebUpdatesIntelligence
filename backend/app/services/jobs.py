"""Application-level job creation used by HTTP endpoints and schedulers."""

from __future__ import annotations

from typing import Any

from backend.app.repository import S3Repository, SourceDisabled
from backend.app.services.ecs import JobDispatcher


def start_source_job(
    repository: S3Repository,
    source: dict[str, Any],
    *,
    operation: str,
    dispatcher: JobDispatcher | None = None,
) -> dict[str, Any]:
    if not source.get("enabled", True):
        raise SourceDisabled("Monitoring is disabled for this source.")
    owner = str(source["owner_name"])
    job = repository.create_job(
        owner,
        operation=operation,
        company_id=int(source["company_id"]),
        source_id=int(source["id"]),
        options={
            "strategy": source["strategy"],
            "acquisition_provider": source.get("acquisition_provider", "auto"),
            "processing_pipeline": source.get("processing_pipeline", "auto"),
        },
    )
    run = repository.create_run(owner, source, operation, str(job["job_id"]))
    job = repository.update_job(str(job["job_id"]), owner, run_id=int(run["id"]))
    return (dispatcher or JobDispatcher(repository)).dispatch(job)


def start_run_all_job(repository: S3Repository, owner: str, *, dispatcher: JobDispatcher | None = None) -> dict[str, Any]:
    job = repository.create_job(owner, operation="run_all", options={"run_enabled_only": True})
    return (dispatcher or JobDispatcher(repository)).dispatch(job)
