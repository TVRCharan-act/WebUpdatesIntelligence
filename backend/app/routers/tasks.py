from fastapi import APIRouter, HTTPException

from backend.app import schemas
from backend.app.auth import CurrentUser, Repository
from backend.app.repository import RecordNotFound


router = APIRouter(prefix="/tasks", tags=["tasks"])


def _owner_filter(user: CurrentUser) -> str | None:
    return None if user.role == "admin" else user.name


@router.get("/{task_id}", response_model=schemas.TaskStatusResponse)
def get_task_status(task_id: str, repository: Repository, user: CurrentUser) -> schemas.TaskStatusResponse:
    try:
        job = repository.get_job(task_id, _owner_filter(user))
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc
    return schemas.TaskStatusResponse(
        task_id=task_id,
        state=str(job["status"]),
        result=job.get("result_summary") or job.get("error"),
        progress=job.get("progress"),
    )
