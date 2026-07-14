from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend.app.repository import S3Repository, iso_now
from backend.app.services.monitor_service import _monitor
from backend.app.storage import InMemoryJsonStorage
from mysignal.providers.pipeline import Candidate, Content


class _NonRelevantAnalyzer:
    def analyze(self, **_kwargs):
        return {"relevant": False}


class _RelevantAnalyzer:
    def analyze(self, **_kwargs):
        return {
            "relevant": True,
            "headline": "Relevant update",
            "summary": "A relevant business update.",
            "model": "test-model",
            "severity": "medium",
            "confidence": "high",
        }


class MonitorLimitTests(unittest.TestCase):
    def setUp(self):
        self.repository = S3Repository(InMemoryJsonStorage(), prefix="sentinel/test/v1")
        self.repository.create_account("alice", "hashed", "customer")
        company = self.repository.create_company("alice", "Acme")
        source = self.repository.create_source(
            "alice",
            {"company_id": company["id"], "url": "https://example.com/news", "strategy": "parent"},
        )
        self.source = self.repository.update_source(
            int(source["id"]),
            "alice",
            baseline_completed_at=iso_now(),
        )

    def test_monitor_processes_a_bounded_batch_and_reports_progress(self):
        candidates = [
            Candidate(url=f"https://example.com/news/{index}", payload={"index": index})
            for index in range(4)
        ]
        run = self.repository.create_run("alice", self.source, "monitor", "job-1")
        acquired: list[str] = []
        progress: list[tuple[str, str, int | None, int | None]] = []

        def acquire(url: str, _provider: str) -> Content:
            acquired.append(url)
            return Content(url=url, title="Update", text="Article content", provider="requests")

        with (
            patch("backend.app.services.monitor_service.discover_candidates", return_value=candidates),
            patch("backend.app.services.monitor_service.acquire_content", side_effect=acquire),
            patch("backend.app.services.monitor_service._build_analyzer", return_value=_NonRelevantAnalyzer()),
            patch(
                "backend.app.services.monitor_service.get_settings",
                return_value=SimpleNamespace(monitor_max_new_urls=2, monitor_url_concurrency=2),
            ),
        ):
            result = _monitor(
                self.repository,
                self.source,
                int(run["id"]),
                "correlation-1",
                lambda stage, message, current, total: progress.append((stage, message, current, total)),
            )

        self.assertEqual(len(acquired), 2)
        self.assertEqual(len(result.new_urls), 4)
        self.assertEqual(len(result.processed_urls), 2)
        self.assertEqual(len(result.deferred_urls), 2)
        self.assertEqual(progress[-1][0], "complete")
        self.assertEqual(progress[-1][2:], (2, 2))

    def test_automatic_mode_sends_new_relevant_insights_through_ses(self):
        self.repository.set_notification_mode("alice", "automatic")
        self.repository.create_recipient(
            "alice",
            int(self.source["company_id"]),
            "alerts@example.com",
        )
        candidate = Candidate(url="https://example.com/news/important", payload={})
        run = self.repository.create_run("alice", self.source, "monitor", "job-automatic")

        with (
            patch("backend.app.services.monitor_service.discover_candidates", return_value=[candidate]),
            patch(
                "backend.app.services.monitor_service.acquire_content",
                return_value=Content(
                    url=candidate.url,
                    title="Important update",
                    text="Article content",
                    provider="requests",
                ),
            ),
            patch("backend.app.services.monitor_service._build_analyzer", return_value=_RelevantAnalyzer()),
            patch(
                "backend.app.services.monitor_service.get_settings",
                return_value=SimpleNamespace(monitor_max_new_urls=5, monitor_url_concurrency=1),
            ),
            patch("backend.app.services.monitor_service.SesEmailSender") as sender,
        ):
            result = _monitor(self.repository, self.source, int(run["id"]), "correlation-automatic")

        self.assertEqual(result.processed_urls, [candidate.url])
        sender.return_value.send.assert_called_once()
        self.assertEqual(sender.return_value.send.call_args.args[1], ["alerts@example.com"])
        self.assertEqual(self.repository.list_insights("alice")[0]["email_status"], "sent")


if __name__ == "__main__":
    unittest.main()
