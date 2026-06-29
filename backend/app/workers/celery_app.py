from time import perf_counter

from celery import Celery
from celery.signals import (
    beat_init,
    task_failure,
    task_postrun,
    task_prerun,
    worker_ready,
    worker_shutdown,
)

from backend.app.config import settings
from backend.app.observability import log_health_event


celery_app = Celery(
    "website_monitor",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "backend.app.workers.monitor_worker",
        "backend.app.workers.scheduler",
    ],
)

celery_app.conf.update(
    task_track_started=True,
    timezone="UTC",
    beat_schedule={
        "monitor-scheduler-every-minute": {
            "task": "monitor.scheduler_tick",
            "schedule": 60.0,
        },
    },
)


_TASK_START_TIMES: dict[str, float] = {}


@worker_ready.connect
def log_worker_ready(sender=None, **kwargs) -> None:
    log_health_event(
        event_type="lifecycle",
        service="celery-worker",
        action="worker_ready",
        status="ok",
        metadata={"sender": repr(sender)},
    )


@worker_shutdown.connect
def log_worker_shutdown(sender=None, **kwargs) -> None:
    log_health_event(
        event_type="lifecycle",
        service="celery-worker",
        action="worker_shutdown",
        status="ok",
        metadata={"sender": repr(sender)},
    )


@beat_init.connect
def log_beat_ready(sender=None, **kwargs) -> None:
    log_health_event(
        event_type="lifecycle",
        service="celery-beat",
        action="beat_ready",
        status="ok",
        metadata={"sender": repr(sender)},
    )


@task_prerun.connect
def log_task_started(task_id=None, task=None, args=None, kwargs=None, **extra) -> None:
    if task_id:
        _TASK_START_TIMES[str(task_id)] = perf_counter()

    log_health_event(
        event_type="celery_task",
        service="celery-worker",
        action=getattr(task, "name", "unknown_task"),
        status="started",
        metadata={
            "task_id": task_id,
            "args": args,
            "kwargs": kwargs,
        },
    )


@task_postrun.connect
def log_task_finished(
    task_id=None,
    task=None,
    retval=None,
    state=None,
    **extra,
) -> None:
    started_at = _TASK_START_TIMES.pop(str(task_id), None) if task_id else None
    duration_ms = (perf_counter() - started_at) * 1000 if started_at else None

    log_health_event(
        event_type="celery_task",
        service="celery-worker",
        action=getattr(task, "name", "unknown_task"),
        status=str(state or "finished").lower(),
        duration_ms=duration_ms,
        metadata={
            "task_id": task_id,
            "state": state,
            "result_preview": repr(retval)[:1000],
        },
    )


@task_failure.connect
def log_task_failed(
    task_id=None,
    exception=None,
    traceback=None,
    sender=None,
    **extra,
) -> None:
    started_at = _TASK_START_TIMES.get(str(task_id)) if task_id else None
    duration_ms = (perf_counter() - started_at) * 1000 if started_at else None

    log_health_event(
        event_type="celery_task",
        service="celery-worker",
        action=getattr(sender, "name", "unknown_task"),
        status="failure",
        duration_ms=duration_ms,
        metadata={
            "task_id": task_id,
            "error": str(exception),
            "traceback_preview": repr(traceback)[:2000],
        },
    )
