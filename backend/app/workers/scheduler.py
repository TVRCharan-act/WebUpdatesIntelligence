import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from backend.app import models
from backend.app.database import SessionLocal
from backend.app.workers.celery_app import celery_app
from backend.app.workers.monitor_worker import monitor_source_task


logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_due(source: models.Source, now: datetime) -> bool:
    if source.last_checked_at is None:
        return True

    last_checked_at = source.last_checked_at
    if last_checked_at.tzinfo is None:
        last_checked_at = last_checked_at.replace(tzinfo=timezone.utc)

    return last_checked_at + timedelta(minutes=source.schedule_minutes) <= now


def _latest_monitor_run(db, source_id: int) -> models.MonitorRun | None:
    return db.scalar(
        select(models.MonitorRun)
        .where(models.MonitorRun.source_id == source_id)
        .order_by(models.MonitorRun.started_at.desc())
        .limit(1)
    )


@celery_app.task(name="monitor.scheduler_tick")
def scheduler_tick() -> dict:
    now = _utc_now()
    queued_source_ids = []
    skipped_source_ids = []
    already_running_source_ids = []
    disabled_source_ids = []

    logger.info("scheduler tick")

    with SessionLocal() as db:
        sources = list(db.scalars(select(models.Source).order_by(models.Source.id)))

        for source in sources:
            if not source.enabled:
                disabled_source_ids.append(source.id)
                logger.info("disabled source skipped: %s", source.id)
                continue

            if not _is_due(source, now):
                skipped_source_ids.append(source.id)
                logger.info("source not due: %s", source.id)
                continue

            latest_run = _latest_monitor_run(db, source.id)
            if latest_run is not None and latest_run.status == "running":
                already_running_source_ids.append(source.id)
                logger.info("source already running: %s", source.id)
                continue

            monitor_source_task.delay(source.id)
            source.last_checked_at = now
            queued_source_ids.append(source.id)
            logger.info("queued source: %s", source.id)

        db.commit()

    return {
        "queued": queued_source_ids,
        "skipped": skipped_source_ids,
        "already_running": already_running_source_ids,
        "disabled": disabled_source_ids,
    }
