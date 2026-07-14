from dataclasses import replace
from threading import Event
import unittest

from backend.app.config import Settings
from backend.app.repository import S3Repository, iso_now
from backend.app.services.ecs import EcsTaskLauncher, JobDispatcher, LocalJobRunner
from backend.app.storage import InMemoryJsonStorage


def settings() -> Settings:
    return Settings(
        environment="test", aws_region="us-east-1", ses_region="us-east-1", s3_bucket="test", storage_backend="memory", s3_prefix="sentinel",
        ecs_cluster="cluster", ecs_task_definition="task:1", ecs_container_name="worker", ecs_launch_type="FARGATE",
        ecs_network_configuration={"awsvpcConfiguration": {"subnets": ["subnet-1"], "securityGroups": ["sg-1"]}},
        scheduler_group_name=None, scheduler_role_arn=None, scheduler_target_arn=None,
        zenrows_api_key="zen", zenrows_js_render=True, zenrows_timeout_seconds=30, zenrows_max_retries=3,
        google_api_key="gemini", google_gemini_model="gemini-3.5-flash",
        openai_api_key=None, openai_model="gpt-5.4", analysis_provider="auto",
        acquisition_pipeline="auto", firecrawl_api_key=None,
        email_sender=None, ses_default_recipients=(), ses_configuration_set=None, auth_secret="secret", auth_cookie_secure=False,
        cors_origins=("http://localhost:3000",), admin_name=None, admin_password=None, bootstrap_customer_accounts=(),
        task_timeout_seconds=900, monitor_max_new_urls=5, monitor_url_concurrency=3,
    )


class FakeEcs:
    def __init__(self):
        self.request = None

    def run_task(self, **kwargs):
        self.request = kwargs
        return {"tasks": [{"taskArn": "arn:aws:ecs:us-east-1:123:task/example"}]}


class EcsDispatchTests(unittest.TestCase):
    def test_launches_fargate_with_application_payload(self):
        client = FakeEcs()
        task_arn = EcsTaskLauncher(settings(), client=client).start({
            "job_id": "job-1", "operation": "monitor", "owner_name": "alice", "company_id": 1, "source_id": 2,
            "run_id": 3, "options": {"strategy": "parent"}, "correlation_id": "corr-1",
        })
        self.assertEqual(task_arn, "arn:aws:ecs:us-east-1:123:task/example")
        self.assertEqual(client.request["launchType"], "FARGATE")
        values = {item["name"]: item["value"] for item in client.request["overrides"]["containerOverrides"][0]["environment"]}
        self.assertEqual(values["SENTINEL_JOB_ID"], "job-1")
        self.assertIn('"operation":"monitor"', values["SENTINEL_JOB_PAYLOAD"])


class LocalDispatchTests(unittest.TestCase):
    def setUp(self):
        self.repository = S3Repository(InMemoryJsonStorage(), prefix="sentinel/test/v1")
        self.repository.create_account("alice", "hashed", "customer")

    def test_local_dispatch_marks_job_starting_then_starts_runner(self):
        class FakeLocalRunner:
            started: dict | None = None

            def start(self, job: dict) -> None:
                self.started = job

        job = self.repository.create_job("alice", operation="run_all")
        runner = FakeLocalRunner()
        updated = JobDispatcher(
            self.repository,
            settings=replace(settings(), task_execution_backend="local"),
            local_runner=runner,
        ).dispatch(job)

        self.assertEqual(updated["status"], "starting")
        self.assertEqual(updated["ecs_task_arn"], f"local://{job['job_id']}")
        self.assertIsNotNone(runner.started)

    def test_local_runner_claims_and_executes_job(self):
        job = self.repository.create_job("alice", operation="run_all")
        finished = Event()

        def complete(repository: S3Repository, claimed: dict) -> dict:
            repository.update_job(
                str(claimed["job_id"]),
                str(claimed["owner_name"]),
                status="succeeded",
                completed_at=iso_now(),
                result_summary={"status": "completed"},
            )
            finished.set()
            return {"status": "completed"}

        LocalJobRunner(self.repository, execute=complete).start(job)

        self.assertTrue(finished.wait(timeout=1))
        self.assertEqual(self.repository.get_job(str(job["job_id"]), "alice")["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
