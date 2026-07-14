from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from backend.app import schemas
from backend.app.auth import CurrentUser, Repository
from backend.app.repository import RecordNotFound


router = APIRouter(prefix="/runs", tags=["runs"])


def _owner_filter(user: CurrentUser) -> str | None:
    return None if user.role == "admin" else user.name


@router.get("", response_model=list[schemas.MonitorRunRead])
def list_monitor_runs(
    repository: Repository,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[dict]:
    return repository.list_runs(_owner_filter(user), limit=limit)


@router.get("/{run_id}", response_model=schemas.MonitorRunWithDiscoveredUrls)
def get_monitor_run(run_id: int, repository: Repository, user: CurrentUser) -> dict:
    try:
        run = repository.get_run(run_id, _owner_filter(user))
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Monitor run not found.") from exc
    return {
        **run,
        "discovered_urls": [
            item
            for item in repository.list_discovered_urls(str(run["owner_name"]), int(run["source_id"]), limit=500)
            if int(item.get("monitor_run_id") or 0) == run_id
        ],
    }
