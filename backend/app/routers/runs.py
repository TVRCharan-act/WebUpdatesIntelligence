from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app import crud, schemas
from backend.app.database import get_db


router = APIRouter(
    prefix="/runs",
    tags=["runs"],
)

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "",
    response_model=list[schemas.MonitorRunRead],
)
def list_monitor_runs(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[schemas.MonitorRunRead]:
    return crud.list_monitor_runs(db, limit)


@router.get(
    "/{run_id}",
    response_model=schemas.MonitorRunWithDiscoveredUrls,
)
def get_monitor_run(
    run_id: int,
    db: DbSession,
) -> schemas.MonitorRunWithDiscoveredUrls:
    monitor_run = crud.get_monitor_run_with_discovered_urls(db, run_id)
    if monitor_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor run not found.",
        )
    return monitor_run
