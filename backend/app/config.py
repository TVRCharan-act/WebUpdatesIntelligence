"""Typed, environment-backed application configuration.

Only this module reads environment variables.  The rest of the application
receives a ``Settings`` instance, which keeps secrets out of routes, storage
code, and browser bundles and makes every integration easy to substitute in a
test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import re
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv


load_dotenv()


class ConfigurationError(RuntimeError):
    """Raised when an operation needs configuration that is not available."""


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _json(name: str, default: dict[str, Any]) -> dict[str, Any]:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"{name} must contain valid JSON.") from exc
    if not isinstance(value, dict):
        raise ConfigurationError(f"{name} must contain a JSON object.")
    return value


@dataclass(frozen=True)
class Settings:
    environment: str
    aws_region: str
    ses_region: str
    s3_bucket: str | None
    storage_backend: str
    s3_prefix: str
    ecs_cluster: str | None
    ecs_task_definition: str | None
    ecs_container_name: str | None
    ecs_launch_type: str
    ecs_network_configuration: dict[str, Any]
    scheduler_group_name: str | None
    scheduler_role_arn: str | None
    scheduler_target_arn: str | None
    zenrows_api_key: str | None
    zenrows_js_render: bool
    zenrows_timeout_seconds: int
    zenrows_max_retries: int
    google_api_key: str | None
    google_gemini_model: str
    openai_api_key: str | None
    openai_model: str
    analysis_provider: str
    acquisition_pipeline: str
    firecrawl_api_key: str | None
    email_sender: str | None
    ses_default_recipients: tuple[str, ...]
    ses_configuration_set: str | None
    auth_secret: str | None
    auth_cookie_secure: bool
    cors_origins: tuple[str, ...]
    admin_name: str | None
    admin_password: str | None
    bootstrap_customer_accounts: tuple[tuple[str, str], ...]
    task_timeout_seconds: int
    monitor_max_new_urls: int
    monitor_url_concurrency: int
    task_execution_backend: str = "ecs"
    feature_flags: dict[str, Any] = field(default_factory=dict)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}

    @property
    def storage_prefix(self) -> str:
        prefix = self.s3_prefix.strip("/")
        return f"{prefix}/{self.environment}/v1" if prefix else f"{self.environment}/v1"

    def require_storage(self) -> None:
        if self.storage_backend == "memory":
            return
        if not self.s3_bucket:
            raise ConfigurationError(
                "S3_BUCKET is required when STORAGE_BACKEND is not 'memory'."
            )

    def require_auth(self) -> None:
        if self.is_production and not self.auth_secret:
            raise ConfigurationError(
                "AUTH_SECRET is required in production to sign session cookies."
            )

    def require_ecs(self) -> None:
        missing = [
            name
            for name, value in (
                ("ECS_CLUSTER", self.ecs_cluster),
                ("ECS_TASK_DEFINITION", self.ecs_task_definition),
            )
            if not value
        ]
        if missing:
            raise ConfigurationError(
                f"ECS task dispatch requires {', '.join(missing)}."
            )

    def require_task_execution_backend(self) -> str:
        backend = self.task_execution_backend.strip().lower()
        if backend not in {"ecs", "local"}:
            raise ConfigurationError(
                "TASK_EXECUTION_BACKEND must be either 'ecs' or 'local'."
            )
        return backend

    def require_zenrows(self) -> None:
        if not self.zenrows_api_key:
            raise ConfigurationError(
                "ZENROWS_API_KEY is required for the ZenRows acquisition provider."
            )

    def require_gemini(self) -> None:
        if not self.google_api_key:
            raise ConfigurationError(
                "GOOGLE_API_KEY is required for Gemini analysis."
            )

    def require_openai(self) -> None:
        if not self.openai_api_key:
            raise ConfigurationError(
                "OPENAI_API_KEY is required for OpenAI analysis."
            )

    def require_analysis_provider(self) -> str:
        provider = self.analysis_provider.strip().lower()
        if provider not in {"auto", "gemini", "openai"}:
            raise ConfigurationError(
                "ANALYSIS_PROVIDER must be 'auto', 'gemini', or 'openai'."
            )
        return provider

    def require_ses(self) -> None:
        if not self.email_sender:
            raise ConfigurationError("SES_FROM_EMAIL is required to send email through SES.")


def load_settings() -> Settings:
    origins = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    )
    customer_indexes = sorted(
        {
            match.group(1)
            for key in os.environ
            if (match := re.fullmatch(r"USER_(\d+)_NAME", key))
        },
        key=int,
    )
    customer_accounts = tuple(
        (name.strip(), password)
        for index in customer_indexes
        if (name := os.getenv(f"USER_{index}_NAME"))
        and (password := os.getenv(f"USER_{index}_PASSWORD"))
    )
    ses_default_recipients = tuple(
        recipient.strip()
        for recipient in os.getenv("SES_DEFAULT_RECIPIENTS", "").split(",")
        if recipient.strip()
    )
    aws_region = os.getenv("AWS_REGION", "us-east-1").strip() or "us-east-1"
    return Settings(
        environment=os.getenv("ENVIRONMENT", "prod").strip() or "prod",
        aws_region=aws_region,
        ses_region=os.getenv("SES_REGION", "").strip() or aws_region,
        s3_bucket=os.getenv("S3_BUCKET") or None,
        storage_backend=os.getenv("STORAGE_BACKEND", "s3").strip().lower() or "s3",
        s3_prefix=os.getenv("S3_PREFIX", "sentinel-actalyst").strip("/"),
        ecs_cluster=os.getenv("ECS_CLUSTER") or None,
        ecs_task_definition=os.getenv("ECS_TASK_DEFINITION") or None,
        ecs_container_name=os.getenv("ECS_CONTAINER_NAME") or None,
        ecs_launch_type=os.getenv("ECS_LAUNCH_TYPE", "FARGATE").upper(),
        ecs_network_configuration=_json("ECS_NETWORK_CONFIGURATION", {}),
        scheduler_group_name=os.getenv("EVENTBRIDGE_SCHEDULER_GROUP") or None,
        scheduler_role_arn=os.getenv("EVENTBRIDGE_SCHEDULER_ROLE_ARN") or None,
        scheduler_target_arn=os.getenv("EVENTBRIDGE_SCHEDULER_TARGET_ARN") or None,
        zenrows_api_key=os.getenv("ZENROWS_API_KEY") or None,
        zenrows_js_render=_bool("ZENROWS_JS_RENDER", True),
        zenrows_timeout_seconds=_int("ZENROWS_TIMEOUT_SECONDS", 30, minimum=1),
        zenrows_max_retries=_int("ZENROWS_MAX_RETRIES", 3, minimum=0),
        google_api_key=os.getenv("GOOGLE_API_KEY") or None,
        google_gemini_model=os.getenv("GOOGLE_GEMINI_MODEL", "gemini-3.5-flash"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
        analysis_provider=os.getenv("ANALYSIS_PROVIDER", "auto").strip().lower() or "auto",
        acquisition_pipeline=os.getenv("DEFAULT_PROCESSING_PIPELINE", "auto"),
        firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY") or os.getenv("fire_crawler_api") or None,
        email_sender=os.getenv("SES_FROM_EMAIL") or None,
        ses_default_recipients=ses_default_recipients,
        ses_configuration_set=os.getenv("SES_CONFIGURATION_SET") or None,
        auth_secret=os.getenv("AUTH_SECRET") or None,
        auth_cookie_secure=_bool("AUTH_COOKIE_SECURE", False),
        cors_origins=origins,
        admin_name=os.getenv("ADMIN_NAME") or None,
        admin_password=os.getenv("ADMIN_PASSWORD") or None,
        bootstrap_customer_accounts=customer_accounts,
        task_timeout_seconds=_int("TASK_TIMEOUT_SECONDS", 900, minimum=30),
        monitor_max_new_urls=_int("MONITOR_MAX_NEW_URLS", 5, minimum=1),
        monitor_url_concurrency=_int("MONITOR_URL_CONCURRENCY", 3, minimum=1),
        task_execution_backend=os.getenv("TASK_EXECUTION_BACKEND", "ecs").strip().lower() or "ecs",
        feature_flags=_json("FEATURE_FLAGS", {}),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def reset_settings_cache() -> None:
    """Test helper for environment-isolated configuration tests."""
    get_settings.cache_clear()
