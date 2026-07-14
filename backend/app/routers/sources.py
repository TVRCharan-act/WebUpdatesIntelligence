from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from backend.app import schemas
from backend.app.auth import CurrentUser, Repository
from backend.app.repository import RecordNotFound, SourceDisabled
from backend.app.storage import StorageError
from backend.app.services.ecs import TaskLaunchError
from backend.app.services.jobs import start_source_job
from mysignal.providers.pipeline import discover_candidates


router = APIRouter(prefix="/sources", tags=["sources"])


def _owner_filter(user: CurrentUser) -> str | None:
    return None if user.role == "admin" else user.name


def _source_or_404(repository: Repository, source_id: int, user: CurrentUser) -> dict:
    try:
        return repository.get_source(source_id, _owner_filter(user))
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Source not found.") from exc


@router.get("", response_model=list[schemas.SourceRead])
def list_sources(repository: Repository, user: CurrentUser) -> list[dict]:
    return repository.list_sources(_owner_filter(user))


@router.get("/{source_id}", response_model=schemas.SourceRead)
def get_source(source_id: int, repository: Repository, user: CurrentUser) -> dict:
    return _source_or_404(repository, source_id, user)


@router.get("/{source_id}/runs", response_model=list[schemas.MonitorRunRead])
def list_source_monitor_runs(
    source_id: int,
    repository: Repository,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 20,
) -> list[dict]:
    source = _source_or_404(repository, source_id, user)
    return repository.list_runs(str(source["owner_name"]), source_id=source_id, limit=limit)


@router.get("/{source_id}/discovered-urls", response_model=list[schemas.DiscoveredUrlRead])
def list_source_discovered_urls(
    source_id: int,
    repository: Repository,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[dict]:
    source = _source_or_404(repository, source_id, user)
    return repository.list_discovered_urls(str(source["owner_name"]), source_id, limit=limit)


@router.get("/{source_id}/summaries", response_model=list[schemas.SummaryRead])
def list_source_summaries(
    source_id: int,
    repository: Repository,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 20,
) -> list[dict]:
    source = _source_or_404(repository, source_id, user)
    return repository.list_insights(str(source["owner_name"]), source_id=source_id, limit=limit)


@router.get("/{source_id}/discovery-preview", response_model=schemas.SourceDiscoveryPreviewRead)
def preview_source_discovery(source_id: int, repository: Repository, user: CurrentUser) -> dict:
    source = _source_or_404(repository, source_id, user)
    try:
        candidates = discover_candidates(source)
    except Exception as exc:
        return {
            "source_id": source_id,
            "source_url": source["url"],
            "strategy": source["strategy"],
            "status": "error",
            "message": str(exc),
            "raw_url_count": 0,
            "content_url_count": 0,
            "already_seen_count": 0,
            "new_candidate_count": 0,
            "urls": [],
        }
    urls = [
        {
            "url": candidate.url,
            "already_seen": bool(repository.seen_record(str(source["owner_name"]), source_id, candidate.url)),
            "source": candidate.payload.get("discovery_provider"),
            "region": None,
            "label": None,
        }
        for candidate in candidates
    ]
    seen = sum(1 for item in urls if item["already_seen"])
    return {
        "source_id": source_id,
        "source_url": source["url"],
        "strategy": source["strategy"],
        "status": "ok",
        "message": "No content URL candidates were found." if not urls else None,
        "raw_url_count": len(urls),
        "content_url_count": len(urls),
        "already_seen_count": seen,
        "new_candidate_count": len(urls) - seen,
        "urls": urls[:200],
    }


@router.post("", response_model=schemas.SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(source: schemas.SourceCreate, repository: Repository, user: CurrentUser) -> dict:
    try:
        repository.get_company(source.company_id, _owner_filter(user))
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Company not found.") from exc
    # A customer always owns monitors they create. An admin creating one selects
    # an existing company, so the company owner remains authoritative.
    company = repository.get_company(source.company_id, _owner_filter(user))
    return repository.create_source(str(company["owner_name"]), source.model_dump(mode="json"))


@router.patch("/{source_id}", response_model=schemas.SourceRead)
def update_source(source_id: int, source: schemas.SourceUpdate, repository: Repository, user: CurrentUser) -> dict:
    _source_or_404(repository, source_id, user)
    values = source.model_dump(exclude_none=True, mode="json")
    if not values:
        raise HTTPException(status_code=400, detail="No source changes were supplied.")
    try:
        return repository.update_source(source_id, _owner_filter(user), **values)
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Source not found.") from exc


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: int, repository: Repository, user: CurrentUser) -> None:
    try:
        repository.delete_source(source_id, _owner_filter(user))
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Source not found.") from exc
    except StorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Storage refused the deletion. Verify S3 DeleteObject permission for this application's prefix.",
        ) from exc


def _queue_source_job(source_id: int, operation: str, repository: Repository, user: CurrentUser) -> schemas.QueuedTaskResponse:
    source = _source_or_404(repository, source_id, user)
    try:
        job = start_source_job(repository, source, operation=operation)
    except SourceDisabled as exc:
        raise HTTPException(
            status_code=409,
            detail="Monitoring is disabled for this source. Enable it before running a check.",
        ) from exc
    except TaskLaunchError as exc:
        raise HTTPException(status_code=503, detail="Monitoring task could not be started. Check job status for details.") from exc
    return schemas.QueuedTaskResponse(task_id=str(job["job_id"]), status="queued")


@router.post("/{source_id}/baseline", response_model=schemas.QueuedTaskResponse)
def run_source_baseline(source_id: int, repository: Repository, user: CurrentUser) -> schemas.QueuedTaskResponse:
    return _queue_source_job(source_id, "baseline", repository, user)


@router.post("/{source_id}/run", response_model=schemas.QueuedTaskResponse)
def run_source_monitor(source_id: int, repository: Repository, user: CurrentUser) -> schemas.QueuedTaskResponse:
    return _queue_source_job(source_id, "monitor", repository, user)
