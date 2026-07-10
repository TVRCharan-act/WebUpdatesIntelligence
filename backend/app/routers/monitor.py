from fastapi import APIRouter

from backend.app import schemas
from backend.app.auth import AdminUser, CurrentUser
from backend.app.services import monitor_service
from backend.app.workers.monitor_worker import run_all_enabled_sources_task


router = APIRouter(
    prefix="/monitor",
    tags=["monitor"],
)


@router.post(
    "/run-all",
    response_model=schemas.QueuedTaskResponse,
)
def run_all_enabled_sources(user: AdminUser) -> schemas.QueuedTaskResponse:
    task = run_all_enabled_sources_task.delay()
    return schemas.QueuedTaskResponse(
        task_id=task.id,
        status="queued",
    )


@router.get(
    "/status",
    response_model=schemas.MonitorStatusSummary,
)
def get_monitor_status(user: CurrentUser) -> schemas.MonitorStatusSummary:
    return monitor_service.get_monitor_status_summary()
