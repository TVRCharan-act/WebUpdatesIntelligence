"""A failing automatic email must not abort URL processing.

If an automatic SES send fails (e.g. an unverified recipient while SES is in the
sandbox), the insight is already persisted and the failure is recorded on it, so
the monitor must still mark the URL as seen. Otherwise the same URL is
re-discovered and re-processed into a duplicate insight on every run.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.app.services import monitor_service
from backend.app.repository import S3Repository, url_fingerprint
from mysignal.notifications.ses_email import EmailDeliveryError

from .conftest import FakeAnalyzer, FakeCandidate, FakeContent, make_source


class FailingSender:
    """SES sender double that always rejects delivery, like an unverified recipient."""

    def send(self, insight: dict, recipients: list[str]) -> str:
        raise EmailDeliveryError("SES delivery failed: MessageRejected (email not verified)")


class RecordingSender:
    """Counts successful sends."""

    def __init__(self) -> None:
        self.calls = 0

    def send(self, insight: dict, recipients: list[str]) -> str:
        self.calls += 1
        return "message-id"


@pytest.fixture
def patched_pipeline(monkeypatch: pytest.MonkeyPatch):
    """Stub the discovery/acquisition/analysis/settings seams around ``_monitor``."""
    url = "https://globex.example/articles/new"

    monkeypatch.setattr(
        monitor_service, "discover_candidates",
        lambda source: [FakeCandidate(url=url, payload={"title": "New"})],
    )
    monkeypatch.setattr(
        monitor_service, "acquire_content",
        lambda candidate_url, provider: FakeContent(title="New", text="body"),
    )
    monkeypatch.setattr(monitor_service, "_build_analyzer", lambda cid: FakeAnalyzer())
    monkeypatch.setattr(monitor_service, "_providers_for", lambda repo, source: ("requests", "gemini"))
    monkeypatch.setattr(monitor_service, "_with_effective_provider", lambda repo, source: source)
    monkeypatch.setattr(
        monitor_service, "get_settings",
        lambda: SimpleNamespace(monitor_max_new_urls=10, monitor_url_concurrency=2),
    )
    return url


def _run_monitor(repo: S3Repository, owner: str, source: dict) -> None:
    run = repo.create_run(owner, source, "check", job_id="job-1")
    monitor_service._monitor(repo, source, int(run["id"]), correlation_id="corr-1")


def test_failed_automatic_email_still_marks_url_seen_and_saves_insight(
    repo: S3Repository, owner: str, patched_pipeline: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = patched_pipeline
    source = make_source(repo, owner)
    sid = int(source["id"])
    repo.set_notification_mode(owner, "automatic")
    monkeypatch.setattr(monitor_service, "SesEmailSender", FailingSender)

    _run_monitor(repo, owner, source)

    insights = repo.list_insights(owner, source_id=sid)
    assert len(insights) == 1, "the insight must be saved even when the email fails"
    assert insights[0]["email_status"] == "failed"
    assert insights[0]["email_error"]
    assert url_fingerprint(url) in repo.seen_url_fingerprints(owner, sid), (
        "URL must be marked seen despite the email failure"
    )


def test_repeated_runs_do_not_reprocess_url_when_email_keeps_failing(
    repo: S3Repository, owner: str, patched_pipeline: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The costly work (acquire + analyze + send) must happen only once.

    ``persist_insight`` is idempotent on (owner, source, url), so a duplicate
    *record* is not the tell. The real harm of the old raise-on-failure bug was
    that a never-seen URL got re-scraped, re-analyzed (LLM spend) and re-emailed
    on *every* run. Counting acquisitions captures that directly.
    """
    source = make_source(repo, owner)
    sid = int(source["id"])
    repo.set_notification_mode(owner, "automatic")
    monkeypatch.setattr(monitor_service, "SesEmailSender", FailingSender)

    acquisitions = {"count": 0}
    real_acquire = monitor_service.acquire_content

    def counting_acquire(candidate_url, provider):
        acquisitions["count"] += 1
        return real_acquire(candidate_url, provider)

    monkeypatch.setattr(monitor_service, "acquire_content", counting_acquire)

    _run_monitor(repo, owner, source)
    _run_monitor(repo, owner, source)  # same URL discovered again
    _run_monitor(repo, owner, source)

    assert acquisitions["count"] == 1, (
        "URL was re-processed on later runs; it should have been marked seen after run 1"
    )
    assert len(repo.list_insights(owner, source_id=sid)) == 1


def test_successful_automatic_email_marks_insight_sent(
    repo: S3Repository, owner: str, patched_pipeline: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_source(repo, owner)
    sid = int(source["id"])
    repo.set_notification_mode(owner, "automatic")
    repo.create_recipient(owner, int(source["company_id"]), "alerts@acme.example")
    sender = RecordingSender()
    monkeypatch.setattr(monitor_service, "SesEmailSender", lambda: sender)

    _run_monitor(repo, owner, source)

    insight = repo.list_insights(owner, source_id=sid)[0]
    assert sender.calls == 1
    assert insight["email_status"] == "sent"
    assert insight["email_sent_at"]


def test_send_insight_if_automatic_swallows_delivery_error(
    repo: S3Repository, owner: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unit-level guard on the fix: the automatic send never propagates."""
    source = make_source(repo, owner)
    discovered = repo.record_discovered_url(
        owner, source, run_id=1, url="https://globex.example/x", payload=None
    )
    insight = repo.persist_insight(
        owner, source, discovered, {"relevant": True, "summary": "s"}
    )
    repo.set_notification_mode(owner, "automatic")
    monkeypatch.setattr(monitor_service, "SesEmailSender", FailingSender)

    # Must not raise.
    monitor_service._send_insight_if_automatic(repo, owner, insight)

    refreshed = repo.get_insight(int(insight["id"]), owner)
    assert refreshed["email_status"] == "failed"
    assert refreshed["email_error"]
