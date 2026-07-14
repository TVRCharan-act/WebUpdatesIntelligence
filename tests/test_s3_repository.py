from datetime import timedelta
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from backend.app.auth import AuthUser, get_current_user
from backend.app.repository import RecordNotFound, S3Repository, SourceDisabled, iso_now, utc_now
from backend.app.schemas import SummaryRead
from backend.app.services.jobs import start_source_job
from backend.app.services.monitor_service import send_insight_email
from backend.app.storage import InMemoryJsonStorage


class S3RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repository = S3Repository(InMemoryJsonStorage(), prefix="sentinel/test/v1")
        self.repository.create_account("alice", "hashed", "customer")
        self.repository.create_account("bob", "hashed", "customer")

    def test_records_are_owner_scoped(self):
        company = self.repository.create_company("alice", "Acme", "high")
        with self.assertRaises(RecordNotFound):
            self.repository.get_company(int(company["id"]), "bob")
        self.assertEqual(self.repository.list_companies("bob"), [])

    def test_seen_state_is_idempotent_and_only_one_record_is_created(self):
        company = self.repository.create_company("alice", "Acme")
        source = self.repository.create_source("alice", {"company_id": company["id"], "url": "https://example.com/news", "strategy": "parent"})
        self.assertTrue(self.repository.mark_seen("alice", int(source["id"]), "https://example.com/news/a"))
        self.assertFalse(self.repository.mark_seen("alice", int(source["id"]), "https://example.com/news/a"))
        self.assertIsNotNone(self.repository.seen_record("alice", int(source["id"]), "https://example.com/news/a"))

    def test_job_claim_is_idempotent_and_terminal_state_is_durable(self):
        job = self.repository.create_job("alice", operation="run_all")
        first = self.repository.claim_job(str(job["job_id"]), "alice", "worker-a")
        second = self.repository.claim_job(str(job["job_id"]), "alice", "worker-b")
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        completed = self.repository.update_job(str(job["job_id"]), "alice", status="succeeded", completed_at=iso_now(), result_summary={"count": 1})
        self.assertEqual(completed["status"], "succeeded")

    def test_job_run_id_is_persisted_before_dispatch(self):
        job = self.repository.create_job("alice", operation="monitor", source_id=42)
        updated = self.repository.update_job(str(job["job_id"]), "alice", run_id=84)
        self.assertEqual(updated["run_id"], 84)
        self.assertEqual(self.repository.get_job(str(job["job_id"]), "alice")["run_id"], 84)

    def test_source_delete_removes_associated_jobs(self):
        company = self.repository.create_company("alice", "Acme")
        source = self.repository.create_source(
            "alice",
            {"company_id": company["id"], "url": "https://example.com/news", "strategy": "parent"},
        )
        self.repository.create_job("alice", operation="monitor", source_id=int(source["id"]))

        self.repository.delete_source(int(source["id"]), "alice")

        self.assertEqual(self.repository.list_sources("alice"), [])
        self.assertEqual(self.repository.list_jobs("alice"), [])

    def test_disabled_source_cannot_queue_manual_monitoring(self):
        company = self.repository.create_company("alice", "Acme")
        source = self.repository.create_source(
            "alice",
            {"company_id": company["id"], "url": "https://example.com/news", "strategy": "parent"},
        )
        disabled = self.repository.update_source(int(source["id"]), "alice", enabled=False)

        with self.assertRaises(SourceDisabled):
            start_source_job(self.repository, disabled, operation="monitor")

        self.assertEqual(self.repository.list_jobs("alice"), [])

    def test_customer_account_delete_removes_owned_data(self):
        company = self.repository.create_company("alice", "Acme")
        source = self.repository.create_source(
            "alice",
            {"company_id": company["id"], "url": "https://example.com/news", "strategy": "parent"},
        )
        self.repository.create_recipient("alice", int(company["id"]), "alerts@example.com")
        self.repository.create_job("alice", operation="monitor", source_id=int(source["id"]))

        self.repository.delete_account("alice")

        self.assertIsNone(self.repository.get_account("alice"))
        self.assertEqual(self.repository.list_companies("alice"), [])
        self.assertEqual(self.repository.list_sources("alice"), [])
        self.assertEqual(self.repository.list_jobs("alice"), [])

    def test_deleted_account_cannot_keep_using_an_existing_session(self):
        self.repository.delete_account("alice")

        with patch("backend.app.auth._decode_session", return_value=AuthUser(name="alice", role="customer")):
            with self.assertRaises(HTTPException) as error:
                get_current_user(self.repository, "previously-valid-session")

        self.assertEqual(error.exception.status_code, 401)

    def test_bootstrap_customer_is_not_recreated_after_deletion(self):
        self.repository.bootstrap_customer_accounts_once((("charlie", "hashed"),))
        self.repository.delete_account("charlie")

        self.repository.bootstrap_customer_accounts_once((("charlie", "hashed"),))

        self.assertIsNone(self.repository.get_account("charlie"))

    def test_due_selection_respects_enabled_cadence(self):
        company = self.repository.create_company("alice", "Acme")
        source = self.repository.create_source("alice", {"company_id": company["id"], "url": "https://example.com/news", "strategy": "parent", "schedule_minutes": 60})
        due = self.repository.due_sources()
        self.assertEqual([item["id"] for item in due], [source["id"]])
        self.repository.update_source(int(source["id"]), "alice", last_checked_at=utc_now().isoformat())
        self.assertEqual(self.repository.due_sources(), [])
        self.repository.update_source(int(source["id"]), "alice", last_checked_at=(utc_now() - timedelta(minutes=61)).isoformat())
        self.assertEqual([item["id"] for item in self.repository.due_sources()], [source["id"]])

    def test_insight_review_accepts_an_exact_string_id(self):
        insight_id = 2**53 + 1
        record = {
            "id": insight_id,
            "owner_name": "alice",
            "company_id": 1,
            "source_id": 1,
            "discovered_url_id": 1,
            "discovered_url": "https://example.com/news/article",
            "summary": "A relevant update.",
            "severity": "medium",
            "confidence": "medium",
            "reviewed_at": None,
            "created_at": iso_now(),
        }
        self.repository.storage.seed(
            [(self.repository._insight_key("alice", insight_id), record)]
        )

        updated = self.repository.update_insight_review(str(insight_id), "alice", True)
        response = SummaryRead.model_validate(updated)

        self.assertIsNotNone(updated["reviewed_at"])
        self.assertEqual(response.id, str(insight_id))

        recipient_id = 42
        self.repository.storage.seed(
            [
                (
                    self.repository._recipient_key("alice", recipient_id),
                    {
                        "id": recipient_id,
                        "owner_name": "alice",
                        "company_id": 1,
                        "email": "alerts@example.com",
                        "enabled": True,
                        "created_at": iso_now(),
                        "updated_at": iso_now(),
                    },
                )
            ]
        )
        with patch("backend.app.services.monitor_service.SesEmailSender") as sender:
            status, _ = send_insight_email(self.repository, str(insight_id), "alice")

        self.assertEqual(status, "sent")
        sender.return_value.send.assert_called_once()
        self.assertEqual(
            self.repository.get_insight(str(insight_id), "alice")["email_status"],
            "sent",
        )


if __name__ == "__main__":
    unittest.main()
