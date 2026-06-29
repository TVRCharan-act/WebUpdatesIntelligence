from backend.app.workers.celery_app import celery_app
from backend.app.services import monitor_service


def _missing_source_result(source_id: int, error: str) -> dict:
    return {
        "status": "failed",
        "source_id": source_id,
        "strategy": "unknown",
        "run_id": None,
        "new_urls": [],
        "processed_urls": [],
        "failed_urls": [],
        "duration_seconds": 0,
        "errors": [error],
    }


@celery_app.task(name="monitor.ping_worker")
def ping_worker() -> str:
    return "pong"


@celery_app.task(name="monitor.baseline_source_task")
def baseline_source_task(source_id: int) -> dict:
    try:
        return monitor_service.run_baseline(source_id).model_dump(mode="json")
    except monitor_service.SourceNotFoundError as exc:
        return _missing_source_result(source_id, str(exc))


@celery_app.task(name="monitor.monitor_source_task")
def monitor_source_task(source_id: int) -> dict:
    try:
        return monitor_service.run_monitor(source_id).model_dump(mode="json")
    except monitor_service.SourceNotFoundError as exc:
        return _missing_source_result(source_id, str(exc))


@celery_app.task(name="monitor.run_all_enabled_sources_task")
def run_all_enabled_sources_task() -> list[dict]:
    return [
        result.model_dump(mode="json")
        for result in monitor_service.run_all_enabled_sources()
    ]
