from fastapi import APIRouter, HTTPException

from backend.app import schemas
from backend.app.auth import AdminUser, CurrentUser, Repository
from backend.app.services.ecs import TaskLaunchError
from backend.app.services.jobs import start_run_all_job
from backend.app.services.monitor_service import get_monitor_status_summary


router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.post("/run-all", response_model=schemas.QueuedTaskResponse)
def run_all_enabled_sources(repository: Repository, user: AdminUser) -> schemas.QueuedTaskResponse:
    try:
        job = start_run_all_job(repository, user.name)
    except TaskLaunchError as exc:
        raise HTTPException(status_code=503, detail="Run-all task could not be started. Check job status for details.") from exc
    return schemas.QueuedTaskResponse(task_id=str(job["job_id"]), status="queued")


@router.get("/status", response_model=schemas.MonitorStatusSummary)
def get_monitor_status(repository: Repository, user: CurrentUser) -> dict:
    return get_monitor_status_summary(repository, None if user.role == "admin" else user.name)
