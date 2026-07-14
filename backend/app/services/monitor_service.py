"""Idempotent monitoring pipeline executed inside ECS tasks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable

from backend.app.config import get_settings
from backend.app.observability import log_health_event
from backend.app.repository import RecordNotFound, S3Repository, SourceDisabled, iso_now
from mysignal.notifications.ses_email import EmailDeliveryError, SesEmailSender
from mysignal.providers.gemini import GeminiAnalyzer
from mysignal.providers.openai_analyzer import OpenAIAnalyzer
from mysignal.providers.pipeline import PipelineError, acquire_content, discover_candidates


class SourceNotFoundError(RuntimeError):
    pass


@dataclass
class MonitorResult:
    status: str
    source_id: int | None
    strategy: str
    run_id: int | None
    new_urls: list[str] = field(default_factory=list)
    processed_urls: list[str] = field(default_factory=list)
    failed_urls: list[str] = field(default_factory=list)
    deferred_urls: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    log_messages: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "source_id": self.source_id,
            "strategy": self.strategy,
            "run_id": self.run_id,
            "new_urls": self.new_urls,
            "processed_urls": self.processed_urls,
            "failed_urls": self.failed_urls,
            "deferred_urls": self.deferred_urls,
            "duration_seconds": round(self.duration_seconds, 3),
            "errors": self.errors,
            "log_messages": self.log_messages,
        }


def _providers_for(source: dict[str, Any]) -> tuple[str, str]:
    pipeline = str(source.get("processing_pipeline") or "auto")
    provider = str(source.get("acquisition_provider") or "auto")
    if pipeline == "zenrows_gemini":
        return "zenrows", "gemini"
    if pipeline in {"current", "auto"}:
        return provider, "gemini"
    raise PipelineError(f"Unsupported processing pipeline: {pipeline}")


class _FallbackAnalyzer:
    """Try the primary analyzer; on any failure, retry once with the fallback."""

    def __init__(self, primary: Any, fallback: Any, correlation_id: str) -> None:
        self.primary = primary
        self.fallback = fallback
        self.correlation_id = correlation_id

    def analyze(self, **kwargs: Any) -> dict[str, Any]:
        try:
            return self.primary.analyze(**kwargs)
        except Exception as exc:
            log_health_event(
                event_type="analysis",
                service="ecs-worker",
                action="fallback",
                status="error",
                correlation_id=self.correlation_id,
                metadata={
                    "primary": type(self.primary).__name__,
                    "fallback": type(self.fallback).__name__,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:500],
                },
            )
            return self.fallback.analyze(**kwargs)


def _build_analyzer(correlation_id: str) -> Any:
    """Pick the analysis model per ANALYSIS_PROVIDER.

    'auto' prefers Gemini and falls back to OpenAI per-URL when both keys are
    configured, so a Gemini outage (quota, billing) degrades gracefully instead
    of dropping insights.
    """
    settings = get_settings()
    provider = settings.require_analysis_provider()
    if provider == "gemini":
        return GeminiAnalyzer(settings)
    if provider == "openai":
        return OpenAIAnalyzer(settings)
    if settings.google_api_key and settings.openai_api_key:
        return _FallbackAnalyzer(GeminiAnalyzer(settings), OpenAIAnalyzer(settings), correlation_id)
    if settings.openai_api_key:
        return OpenAIAnalyzer(settings)
    return GeminiAnalyzer(settings)


ProgressReporter = Callable[[str, str, int | None, int | None], None]


def _baseline(
    repository: S3Repository,
    source: dict[str, Any],
    run_id: int,
    correlation_id: str,
    report_progress: ProgressReporter | None = None,
) -> MonitorResult:
    started = perf_counter()
    owner = str(source["owner_name"])
    if report_progress:
        report_progress("discovering", "Crawling the source to establish its baseline.", None, None)
    candidates = discover_candidates(source)
    stored: list[str] = []
    if report_progress:
        report_progress("baselining", f"Recording {len(candidates)} discovered URLs as seen.", 0, len(candidates))
    for index, candidate in enumerate(candidates, start=1):
        repository.record_discovered_url(owner, source, run_id, candidate.url, candidate.payload)
        repository.mark_seen(owner, int(source["id"]), candidate.url, baseline=True)
        stored.append(candidate.url)
        if report_progress and (index == len(candidates) or index % 25 == 0):
            report_progress("baselining", f"Recording baseline URLs ({index}/{len(candidates)}).", index, len(candidates))
    repository.update_source(int(source["id"]), owner, baseline_completed_at=iso_now(), last_checked_at=iso_now())
    if report_progress:
        report_progress("complete", f"Baseline complete: recorded {len(stored)} URLs without scraping articles.", len(stored), len(stored))
    result = MonitorResult(
        status="completed",
        source_id=int(source["id"]),
        strategy=str(source["strategy"]),
        run_id=run_id,
        new_urls=stored,
        duration_seconds=perf_counter() - started,
        log_messages=[f"Baseline stored {len(stored)} URL(s); no historical insights or email were generated."],
    )
    log_health_event(
        event_type="monitor",
        service="ecs-worker",
        action="baseline",
        status="ok",
        correlation_id=correlation_id,
        metadata={"source_id": source["id"], "run_id": run_id, "baseline_url_count": len(stored)},
    )
    return result


def _send_insight_if_automatic(repository: S3Repository, owner: str, insight: dict[str, Any]) -> None:
    if repository.get_notification_mode(owner) != "automatic":
        return
    claimed = repository.claim_email_delivery(int(insight["id"]), owner)
    if claimed is None:
        return
    recipients = [
        str(item["email"])
        for item in repository.list_recipients(owner, company_id=int(insight["company_id"]))
        if item.get("enabled")
    ]
    try:
        SesEmailSender().send(claimed, recipients)
        repository.complete_email_delivery(int(insight["id"]), owner, sent=True)
    except EmailDeliveryError as exc:
        repository.complete_email_delivery(int(insight["id"]), owner, sent=False, error=str(exc))
        raise


def send_insight_email(repository: S3Repository, insight_id: int | str, owner: str | None) -> tuple[str, str]:
    insight = repository.get_insight(insight_id, owner)
    actual_owner = str(insight["owner_name"])
    claimed = repository.claim_email_delivery(insight_id, actual_owner)
    if claimed is None:
        return "skipped", "This insight has already been sent or is being delivered."
    recipients = [
        str(item["email"])
        for item in repository.list_recipients(actual_owner, company_id=int(insight["company_id"]))
        if item.get("enabled")
    ]
    try:
        SesEmailSender().send(claimed, recipients)
        repository.complete_email_delivery(insight_id, actual_owner, sent=True)
    except EmailDeliveryError as exc:
        repository.complete_email_delivery(insight_id, actual_owner, sent=False, error=str(exc))
        raise
    return "sent", "Email sent through Amazon SES."


def _monitor(
    repository: S3Repository,
    source: dict[str, Any],
    run_id: int,
    correlation_id: str,
    report_progress: ProgressReporter | None = None,
) -> MonitorResult:
    if not source.get("baseline_completed_at"):
        return _baseline(repository, source, run_id, correlation_id, report_progress)
    started = perf_counter()
    owner = str(source["owner_name"])
    settings = get_settings()
    if report_progress:
        report_progress("discovering", "Crawling the source for newly published URLs.", None, None)
    candidates = discover_candidates(source)
    new_candidates = [
        candidate
        for candidate in candidates
        if not repository.seen_record(owner, int(source["id"]), candidate.url)
    ]
    new_urls = [candidate.url for candidate in new_candidates]
    candidates_to_process = new_candidates[: settings.monitor_max_new_urls]
    deferred_urls = [candidate.url for candidate in new_candidates[settings.monitor_max_new_urls :]]
    processed: list[str] = []
    failed: list[str] = []
    errors: list[str] = []
    provider, _analysis_provider = _providers_for(source)
    analyzer = _build_analyzer(correlation_id)

    if report_progress:
        if candidates_to_process:
            report_progress(
                "processing",
                f"Found {len(new_urls)} new URLs; processing {len(candidates_to_process)} now.",
                0,
                len(candidates_to_process),
            )
        else:
            report_progress("complete", "No new URLs were found.", 0, 0)

    def process_candidate(candidate: Any) -> tuple[str, str | None]:
        try:
            discovered = repository.record_discovered_url(owner, source, run_id, candidate.url, candidate.payload)
            content = acquire_content(candidate.url, provider)
            analysis = analyzer.analyze(title=content.title, content=content.text, source_url=candidate.url)
            if analysis["relevant"]:
                insight = repository.persist_insight(owner, source, discovered, analysis)
                _send_insight_if_automatic(repository, owner, insight)
            # A candidate is only made seen after all required acquisition and
            # analysis steps succeed. Non-relevant content was successfully
            # processed, so it is intentionally eligible to be marked seen.
            repository.mark_seen(owner, int(source["id"]), candidate.url, insight_id=(int(insight["id"]) if analysis["relevant"] else None))
            return candidate.url, None
        except Exception as exc:
            log_health_event(
                event_type="url_processing",
                service="ecs-worker",
                action="process",
                status="error",
                correlation_id=correlation_id,
                metadata={"source_id": source["id"], "url": candidate.url, "error_type": type(exc).__name__},
            )
            return candidate.url, str(exc)

    if candidates_to_process:
        max_workers = min(settings.monitor_url_concurrency, len(candidates_to_process))
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="sentinel-url") as executor:
            futures = [executor.submit(process_candidate, candidate) for candidate in candidates_to_process]
            for completed_count, future in enumerate(as_completed(futures), start=1):
                url, error = future.result()
                if error is None:
                    processed.append(url)
                else:
                    failed.append(url)
                    errors.append(f"{url}: {error}")
                if report_progress:
                    report_progress(
                        "processing",
                        f"Processed {completed_count}/{len(candidates_to_process)} new URLs.",
                        completed_count,
                        len(candidates_to_process),
                    )
    repository.update_source(int(source["id"]), owner, last_checked_at=iso_now())
    if report_progress:
        report_progress(
            "complete",
            f"Processed {len(processed)} of {len(candidates_to_process)} new URLs"
            + (f"; {len(deferred_urls)} will be picked up next check." if deferred_urls else "."),
            len(candidates_to_process),
            len(candidates_to_process),
        )
    return MonitorResult(
        status="completed" if not failed else "partially_succeeded",
        source_id=int(source["id"]),
        strategy=str(source["strategy"]),
        run_id=run_id,
        new_urls=new_urls,
        processed_urls=processed,
        failed_urls=failed,
        deferred_urls=deferred_urls,
        duration_seconds=perf_counter() - started,
        errors=errors,
        log_messages=[
            f"Discovered {len(new_urls)} new URL(s); processed {len(processed)} now"
            + (f" and deferred {len(deferred_urls)}." if deferred_urls else ".")
        ],
    )


def _run_source_job(repository: S3Repository, job: dict[str, Any]) -> MonitorResult:
    owner = str(job["owner_name"])
    job_id = str(job["job_id"])
    source_id = job.get("source_id")
    run_id = job.get("run_id")
    if not isinstance(source_id, int) or not isinstance(run_id, int):
        raise SourceNotFoundError("A source job is missing its source or run identifier.")
    try:
        source = repository.get_source(source_id, owner)
    except RecordNotFound as exc:
        raise SourceNotFoundError("Source not found.") from exc
    if not source.get("enabled", True):
        message = "Monitoring was disabled before this job started."
        repository.update_run(run_id, owner, status="cancelled", finished_at=iso_now(), error=message)
        raise SourceDisabled(message)

    def report_progress(stage: str, message: str, current: int | None, total: int | None) -> None:
        progress: dict[str, Any] = {"stage": stage, "message": message}
        if current is not None:
            progress["current"] = current
        if total is not None:
            progress["total"] = total
        repository.update_job(job_id, owner, progress=progress)

    repository.update_run(run_id, owner, status="running")
    report_progress("starting", "Preparing the source check.", None, None)
    try:
        result = (
            _baseline(repository, source, run_id, str(job["correlation_id"]), report_progress)
            if job["operation"] == "baseline"
            else _monitor(repository, source, run_id, str(job["correlation_id"]), report_progress)
        )
        repository.update_run(
            run_id,
            owner,
            status="completed" if result.status == "completed" else "partially_succeeded",
            finished_at=iso_now(),
            result_summary=result.as_dict(),
        )
        return result
    except SourceDisabled as exc:
        result = {"status": "cancelled", "message": str(exc)}
        repository.update_job(
            job_id,
            owner,
            status="cancelled",
            completed_at=iso_now(),
            result_summary=result,
        )
        return result
    except Exception as exc:
        repository.update_run(run_id, owner, status="failed", finished_at=iso_now(), error=str(exc))
        raise


def execute_job(repository: S3Repository, job: dict[str, Any]) -> dict[str, Any]:
    """Run a claimed ECS job and make terminal state durable even on failures."""
    owner = str(job["owner_name"])
    job_id = str(job["job_id"])
    try:
        if job["operation"] in {"baseline", "monitor"}:
            result: Any = _run_source_job(repository, job).as_dict()
            status = "succeeded" if result["status"] == "completed" else "partially_succeeded"
        elif job["operation"] == "run_all":
            results: list[dict[str, Any]] = []
            for source in repository.list_sources(owner, limit=10000):
                if not source.get("enabled"):
                    continue
                run = repository.create_run(owner, source, "monitor", job_id)
                child = {**job, "operation": "monitor", "source_id": int(source["id"]), "run_id": int(run["id"])}
                results.append(_run_source_job(repository, child).as_dict())
            result = results
            status = "partially_succeeded" if any(item["status"] != "completed" for item in results) else "succeeded"
        else:
            raise ValueError(f"Unsupported job operation: {job['operation']}")
        repository.update_job(job_id, owner, status=status, completed_at=iso_now(), result_summary=result)
        return result
    except Exception as exc:
        repository.update_job(
            job_id,
            owner,
            status="failed",
            completed_at=iso_now(),
            error={"message": str(exc), "safe_message": "Monitoring task failed. It may be retried."},
        )
        log_health_event(
            event_type="monitor",
            service="ecs-worker",
            action=str(job["operation"]),
            status="error",
            correlation_id=str(job["correlation_id"]),
            metadata={"job_id": job_id, "error_type": type(exc).__name__},
        )
        raise


def get_monitor_status_summary(repository: S3Repository, owner: str | None) -> dict[str, int]:
    return repository.monitor_status(owner)
