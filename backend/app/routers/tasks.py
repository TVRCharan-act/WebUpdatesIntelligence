from fastapi import APIRouter

from backend.app import schemas
from backend.app.workers.celery_app import celery_app


router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
)


@router.get(
    "/{task_id}",
    response_model=schemas.TaskStatusResponse,
)
def get_task_status(task_id: str) -> schemas.TaskStatusResponse:
    task_result = celery_app.AsyncResult(task_id)

    result = None
    if task_result.successful():
        result = task_result.result
    elif task_result.failed():
        result = {
            "error": str(task_result.result),
        }

    return schemas.TaskStatusResponse(
        task_id=task_id,
        state=task_result.state,
        result=result,
    )
