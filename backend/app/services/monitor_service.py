from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, time, timezone
from threading import Lock
from time import perf_counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app import crud, models, schemas
from backend.app.database import SessionLocal
from mysignal.discovery.api_discovery import (
    discover_js_bundle_sources,
    normalize_api_url,
)
from mysignal.discovery.page_links import normalize_page_url
from mysignal.summarizers.insight_format import parse_insight_output
from mysignal.monitoring.inventory_store import (
    load_seen_url_records,
    load_tracked_recursive_targets,
)
from mysignal.workflows import new_url_processor
from mysignal.workflows.api_monitor import (
    baseline_seen_urls_from_apis,
    discover_new_urls_from_apis,
)
from mysignal.workflows.feed_monitor import (
    baseline_seen_urls_from_feeds,
    discover_new_urls_from_feeds,
    normalize_feed_url,
)
from mysignal.workflows.parent_monitor import (
    baseline_seen_urls_from_parents,
    discover_new_urls_from_parents,
)


VALID_STRATEGIES = {
    "parent",
    "feed",
    "api",
}
SUMMARY_CAPTURE_LOCK = Lock()


class SourceNotFoundError(ValueError):
    pass


@dataclass
class CapturedArticle:
    title: str | None = None
    summary: str | None = None
    model: str | None = None
    severity: str = "medium"
    confidence: str = "medium"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _duration(started_at: float) -> float:
    return round(perf_counter() - started_at, 3)


def _source_query(source_id: int):
    return (
        select(models.Source)
        .where(models.Source.id == source_id)
        .options(
            selectinload(models.Source.company).selectinload(
                models.Company.notification_recipients
            )
        )
    )


def _get_source(db: Session, source_id: int) -> models.Source:
    source = db.scalar(_source_query(source_id))
    if source is None:
        raise SourceNotFoundError(f"Source {source_id} was not found.")

    if source.strategy not in VALID_STRATEGIES:
        raise ValueError(f"Unsupported source strategy: {source.strategy}")

    return source


def _create_run(db: Session, source: models.Source) -> models.MonitorRun:
    monitor_run = models.MonitorRun(
        source_id=source.id,
        status="running",
        started_at=_utc_now(),
    )
    db.add(monitor_run)
    db.commit()
    db.refresh(monitor_run)
    return monitor_run


def _complete_run(db: Session, monitor_run: models.MonitorRun) -> None:
    monitor_run.status = "completed"
    monitor_run.finished_at = _utc_now()
    db.commit()
    db.refresh(monitor_run)


def _fail_run(db: Session, monitor_run: models.MonitorRun, error: str) -> None:
    monitor_run.status = "failed"
    monitor_run.finished_at = _utc_now()
    monitor_run.error = error
    db.commit()
    db.refresh(monitor_run)


def _source_has_seen_records(source: models.Source) -> bool:
    source_url = _normalized_source_url(source)
    records = load_seen_url_records()

    for record in records.values():
        if not isinstance(record, dict):
            continue

        if source.strategy == "parent" and record.get("parent_url") == source_url:
            return True

        if source.strategy == "feed" and record.get("feed_url") == source_url:
            return True

        if source.strategy == "api" and record.get("api_url") == source_url:
            return True

    return False


def _log_discovered_url(
    db: Session,
    *,
    source_id: int,
    monitor_run_id: int,
    url: str,
    payload: dict,
) -> models.DiscoveredUrl:
    discovered_url = models.DiscoveredUrl(
        source_id=source_id,
        monitor_run_id=monitor_run_id,
        url=url,
        payload=payload,
    )
    db.add(discovered_url)
    db.commit()
    db.refresh(discovered_url)
    return discovered_url


def _log_summary(
    db: Session,
    *,
    discovered_url_id: int,
    article: CapturedArticle,
    email_status: str = "pending",
    email_error: str | None = None,
) -> None:
    if not article.summary:
        return

    db.add(
        models.Summary(
            discovered_url_id=discovered_url_id,
            title=article.title,
            summary=article.summary,
            model=article.model,
            severity=article.severity,
            confidence=article.confidence,
            email_status=email_status,
            email_sent_at=_utc_now() if email_status == "sent" else None,
            email_error=email_error,
        )
    )
    db.commit()


def _email_notification_mode(db: Session) -> str:
    return crud.get_email_notification_mode(db)


def _monitor_result(
    *,
    status: str,
    source: models.Source,
    monitor_run: models.MonitorRun,
    started_at: float,
    new_urls: list[str] | None = None,
    processed_urls: list[str] | None = None,
    failed_urls: list[str] | None = None,
    errors: list[str] | None = None,
    log_messages: list[str] | None = None,
) -> schemas.MonitorResult:
    return schemas.MonitorResult(
        status=status,
        source_id=source.id,
        strategy=source.strategy,
        run_id=monitor_run.id,
        new_urls=new_urls or [],
        processed_urls=processed_urls or [],
        failed_urls=failed_urls or [],
        duration_seconds=_duration(started_at),
        errors=errors or [],
        log_messages=log_messages or [],
    )


def _processing_log_messages(
    *,
    source: models.Source,
    new_urls: list[str],
    processed_urls: list[str],
    failed_urls: list[str],
    processing_errors: list[str],
) -> list[str]:
    messages = [
        (
            f"Successful crawl: source {source.id} discovered "
            f"{len(new_urls)} new URL(s)."
        )
    ]

    if not new_urls:
        messages.append("Firecrawl not needed: no new URLs to scrape.")
        messages.append("OpenAI not needed: no new URLs to summarize.")
        return messages

    if processed_urls:
        messages.append(
            f"Firecrawl active: scraped {len(processed_urls)} URL(s)."
        )
        messages.append(
            f"OpenAI active: summarized {len(processed_urls)} URL(s)."
        )

    if failed_urls:
        if any("ip_not_authorized" in error for error in processing_errors):
            messages.append(
                "Firecrawl active: page scraping completed before OpenAI summarization."
            )
            messages.append(
                "OpenAI active but rejected request: Your IP is not authorized to make this request."
            )
        elif processing_errors:
            messages.append("Processing failed after new URL discovery.")
            messages.append(f"Latest processing error: {processing_errors[-1]}")
        else:
            messages.append("Processing failed for one or more new URLs.")

    return messages


def _baseline_source(
    db: Session,
    source: models.Source,
) -> dict:
    if source.strategy == "parent":
        _refresh_js_bundle_sources(
            db,
            source,
        )

    if source.strategy == "parent":
        return baseline_seen_urls_from_parents([source])

    if source.strategy == "feed":
        return baseline_seen_urls_from_feeds([source.url])

    if source.strategy == "api":
        return baseline_seen_urls_from_apis([source.url])

    raise ValueError(f"Unsupported source strategy: {source.strategy}")


def _discover_source(
    db: Session,
    source: models.Source,
) -> tuple[list[str], dict]:
    if source.strategy == "parent":
        _refresh_js_bundle_sources(
            db,
            source,
        )

    if source.strategy == "parent":
        return discover_new_urls_from_parents([source], store_new_urls=False)

    if source.strategy == "feed":
        return discover_new_urls_from_feeds([source.url], store_new_urls=False)

    if source.strategy == "api":
        return discover_new_urls_from_apis([source.url], store_new_urls=False)

    raise ValueError(f"Unsupported source strategy: {source.strategy}")


def _normalized_source_url(source: models.Source) -> str:
    if source.strategy == "feed":
        return normalize_feed_url(source.url)

    if source.strategy == "api":
        return normalize_api_url(source.url)

    return normalize_page_url(source.url)


def _refresh_js_bundle_sources(
    db: Session,
    source: models.Source,
) -> None:
    if not source.trace_js:
        return

    source_url = normalize_page_url(
        source.url,
    )
    detected_sources = discover_js_bundle_sources(
        source_url,
        script_sources=source.js_bundle_sources,
    )

    if detected_sources == source.js_bundle_sources:
        return

    crud.update_source_js_bundle_sources(
        db,
        source,
        detected_sources,
    )


def _recipients_for_source(source: models.Source) -> list[str]:
    company_recipients = sorted(
        recipient.email
        for recipient in source.company.notification_recipients
        if recipient.enabled
    )
    if company_recipients:
        return company_recipients

    source_url = _normalized_source_url(source)

    for target in load_tracked_recursive_targets():
        if target.strategy != source.strategy:
            continue

        target_url = (
            normalize_feed_url(target.url)
            if target.strategy == "feed"
            else normalize_api_url(target.url)
            if target.strategy == "api"
            else normalize_page_url(target.url)
        )

        if target_url == source_url:
            return target.recipients

    return []


@contextmanager
def _capture_article() -> Callable[[], CapturedArticle | None]:
    original_summarize = new_url_processor.summarize_new_url
    captured_article: CapturedArticle | None = None

    def summarize_and_capture(url: str):
        nonlocal captured_article
        article = original_summarize(url)

        # Split the raw model output into a clean headline + paragraph and the
        # severity/confidence signals. Rewrite the article in place with the
        # clean prose so downstream consumers (email, logs) get the paragraph,
        # not the labeled scaffolding.
        parsed = parse_insight_output(article.summary)
        body = str(parsed["body"]) or (article.summary or "")
        headline = parsed["headline"] or article.title
        if article.summary:
            article.summary = body
            if headline:
                article.title = headline

        captured_article = CapturedArticle(
            title=headline or article.title,
            summary=body if article.summary else article.summary,
            model="gpt-5.4" if article.summary else None,
            severity=str(parsed["severity"]),
            confidence=str(parsed["confidence"]),
        )
        return article

    with SUMMARY_CAPTURE_LOCK:
        new_url_processor.summarize_new_url = summarize_and_capture
        try:
            yield lambda: captured_article
        finally:
            new_url_processor.summarize_new_url = original_summarize


def run_baseline(source_id: int) -> schemas.MonitorResult:
    started_at = perf_counter()

    with SessionLocal() as db:
        source = _get_source(db, source_id)
        monitor_run = _create_run(db, source)

        try:
            added_records = _baseline_source(
                db,
                source,
            )
            new_urls = sorted(added_records)

            for url in new_urls:
                _log_discovered_url(
                    db,
                    source_id=source.id,
                    monitor_run_id=monitor_run.id,
                    url=url,
                    payload=added_records[url],
                )

            _complete_run(db, monitor_run)
            return _monitor_result(
                status="completed",
                source=source,
                monitor_run=monitor_run,
                started_at=started_at,
                new_urls=new_urls,
                processed_urls=[],
                failed_urls=[],
                log_messages=[
                    (
                        f"Successful baseline crawl: source {source.id} stored "
                        f"{len(new_urls)} URL(s)."
                    ),
                    "Firecrawl not needed: baseline stores discovered URLs only.",
                    "OpenAI not needed: baseline does not summarize URLs.",
                ],
            )
        except Exception as exc:
            _fail_run(db, monitor_run, str(exc))
            return _monitor_result(
                status="failed",
                source=source,
                monitor_run=monitor_run,
                started_at=started_at,
                errors=[str(exc)],
            )


def run_monitor(source_id: int) -> schemas.MonitorResult:
    started_at = perf_counter()

    with SessionLocal() as db:
        source = _get_source(db, source_id)
        needs_baseline_seed = not _source_has_seen_records(source)
        monitor_run = _create_run(db, source)

        try:
            if needs_baseline_seed:
                added_records = _baseline_source(
                    db,
                    source,
                )
                seeded_urls = sorted(added_records)

                for url in seeded_urls:
                    _log_discovered_url(
                        db,
                        source_id=source.id,
                        monitor_run_id=monitor_run.id,
                        url=url,
                        payload=added_records[url],
                    )

                _complete_run(db, monitor_run)
                return _monitor_result(
                    status="completed",
                    source=source,
                    monitor_run=monitor_run,
                    started_at=started_at,
                    new_urls=seeded_urls,
                    processed_urls=[],
                    failed_urls=[],
                    log_messages=[
                        (
                            f"Baseline seed: source {source.id} stored "
                            f"{len(seeded_urls)} existing URL(s)."
                        ),
                        "Firecrawl not activated: baseline seed only stores existing URLs.",
                        "OpenAI not activated: baseline seed does not summarize existing URLs.",
                    ],
                )

            new_urls, new_records = _discover_source(
                db,
                source,
            )
            processed_urls = []
            failed_urls = []
            processing_errors = []
            recipients = _recipients_for_source(source)
            notification_mode = _email_notification_mode(db)
            send_email_automatically = notification_mode == "automatic"

            for url in new_urls:
                discovered_url = _log_discovered_url(
                    db,
                    source_id=source.id,
                    monitor_run_id=monitor_run.id,
                    url=url,
                    payload=new_records[url],
                )

                with _capture_article() as captured_article:
                    email_result: dict = {}
                    processed = new_url_processor.process_new_url_record(
                        url=url,
                        record=new_records[url],
                        recipients=recipients,
                        processing_errors=processing_errors,
                        send_email=send_email_automatically,
                        email_result=email_result,
                    )

                if processed:
                    processed_urls.append(url)
                    article = captured_article()
                    if article is not None:
                        email_status = str(
                            email_result.get(
                                "status",
                                "pending" if not send_email_automatically else "skipped",
                            )
                        )
                        _log_summary(
                            db,
                            discovered_url_id=discovered_url.id,
                            article=article,
                            email_status=email_status,
                            email_error=email_result.get("error"),
                        )
                else:
                    failed_urls.append(url)

            _complete_run(db, monitor_run)
            unique_processing_errors = list(dict.fromkeys(processing_errors))
            if failed_urls:
                unique_processing_errors.append(
                    f"{len(failed_urls)} URL(s) failed during article processing or summarization."
                )
                unique_processing_errors.append(
                    "Check url_processing events in logs/app-health.jsonl for the exact failure."
                )

            return _monitor_result(
                status="completed",
                source=source,
                monitor_run=monitor_run,
                started_at=started_at,
                new_urls=new_urls,
                processed_urls=processed_urls,
                failed_urls=failed_urls,
                errors=unique_processing_errors,
                log_messages=_processing_log_messages(
                    source=source,
                    new_urls=new_urls,
                    processed_urls=processed_urls,
                    failed_urls=failed_urls,
                    processing_errors=unique_processing_errors,
                ),
            )
        except Exception as exc:
            _fail_run(db, monitor_run, str(exc))
            return _monitor_result(
                status="failed",
                source=source,
                monitor_run=monitor_run,
                started_at=started_at,
                errors=[str(exc)],
            )


def run_all_enabled_sources() -> list[schemas.MonitorResult]:
    with SessionLocal() as db:
        source_ids = list(
            db.scalars(
                select(models.Source.id)
                .where(models.Source.enabled.is_(True))
                .order_by(models.Source.id)
            )
        )

    return [
        run_monitor(source_id)
        for source_id in source_ids
    ]


def get_monitor_status() -> list[schemas.MonitorResult]:
    with SessionLocal() as db:
        monitor_runs = list(
            db.scalars(
                select(models.MonitorRun)
                .options(
                    selectinload(models.MonitorRun.source),
                    selectinload(models.MonitorRun.discovered_urls),
                )
                .order_by(models.MonitorRun.started_at.desc())
                .limit(25)
            )
        )

        results = []

        for monitor_run in monitor_runs:
            finished_at = monitor_run.finished_at or _utc_now()
            duration_seconds = round(
                (finished_at - monitor_run.started_at).total_seconds(),
                3,
            )
            new_urls = [
                discovered_url.url
                for discovered_url in monitor_run.discovered_urls
            ]

            results.append(
                schemas.MonitorResult(
                    status=monitor_run.status,
                    source_id=monitor_run.source_id,
                    strategy=monitor_run.source.strategy if monitor_run.source else "unknown",
                    run_id=monitor_run.id,
                    new_urls=new_urls,
                    processed_urls=[],
                    failed_urls=[],
                    duration_seconds=duration_seconds,
                    errors=[monitor_run.error] if monitor_run.error else [],
                )
            )

        return results


def get_monitor_status_summary() -> schemas.MonitorStatusSummary:
    now = _utc_now()
    today_start = datetime.combine(
        now.date(),
        time.min,
        tzinfo=timezone.utc,
    )

    with SessionLocal() as db:
        enabled_sources = db.scalar(
            select(func.count())
            .select_from(models.Source)
            .where(models.Source.enabled.is_(True))
        ) or 0
        queued = db.scalar(
            select(func.count())
            .select_from(models.MonitorRun)
            .where(models.MonitorRun.status == "queued")
        ) or 0
        running = db.scalar(
            select(func.count())
            .select_from(models.MonitorRun)
            .where(models.MonitorRun.status == "running")
        ) or 0
        completed_today = db.scalar(
            select(func.count())
            .select_from(models.MonitorRun)
            .where(
                models.MonitorRun.status == "completed",
                models.MonitorRun.finished_at >= today_start,
            )
        ) or 0
        failed_today = db.scalar(
            select(func.count())
            .select_from(models.MonitorRun)
            .where(
                models.MonitorRun.status == "failed",
                models.MonitorRun.finished_at >= today_start,
            )
        ) or 0

    return schemas.MonitorStatusSummary(
        enabled_sources=enabled_sources,
        queued=queued,
        running=running,
        completed_today=completed_today,
        failed_today=failed_today,
    )
