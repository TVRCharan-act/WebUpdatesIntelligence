from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class HealthCheck(BaseModel):
    status: str


class DiscoveryHealthRead(BaseModel):
    status: str
    openai_configured: bool
    openai_model: str
    browser_tracing_available: bool
    adapter_cache_path: str
    adapter_cache_exists: bool
    cached_adapter_count: int
    recent_discovery_event_count: int
    recent_discovery_error_count: int
    heavy_discovery_lock: dict[str, Any] = Field(default_factory=dict)
    limits: dict[str, Any] = Field(default_factory=dict)


class MonitorResult(BaseModel):
    status: str
    source_id: int
    strategy: str
    run_id: int
    new_urls: list[str] = Field(default_factory=list)
    processed_urls: list[str] = Field(default_factory=list)
    failed_urls: list[str] = Field(default_factory=list)
    duration_seconds: float
    errors: list[str] = Field(default_factory=list)
    log_messages: list[str] = Field(default_factory=list)


class QueuedTaskResponse(BaseModel):
    task_id: str
    status: Literal["queued"]


class TaskStatusResponse(BaseModel):
    task_id: str
    state: str
    result: Any = None


class MonitorStatusSummary(BaseModel):
    enabled_sources: int
    queued: int
    running: int
    completed_today: int
    failed_today: int


class MonitorRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None


class DiscoveredUrlRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    monitor_run_id: int | None = None
    url: str
    payload: dict[str, Any] | None = None
    discovered_at: datetime


class SummaryRead(BaseModel):
    id: int
    discovered_url_id: int
    discovered_url: str
    title: str | None = None
    summary: str
    model: str | None = None
    severity: Literal["low", "medium", "high"] = "medium"
    confidence: Literal["low", "medium", "high"] = "medium"
    reviewed_at: datetime | None = None
    email_status: str = "pending"
    email_sent_at: datetime | None = None
    email_error: str | None = None
    created_at: datetime


class EmailNotificationSettingsRead(BaseModel):
    mode: Literal["manual", "automatic"]


class EmailNotificationSettingsUpdate(BaseModel):
    mode: Literal["manual", "automatic"]


class EmailSendResult(BaseModel):
    summary_id: int
    status: Literal["sent", "failed", "skipped"]
    message: str


class NotificationRecipientBase(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    enabled: bool = True

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address.")
        return value


class NotificationRecipientCreate(NotificationRecipientBase):
    pass


class NotificationRecipientUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=320)
    enabled: bool | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address.")
        return value


class NotificationRecipientRead(NotificationRecipientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    created_at: datetime
    updated_at: datetime


class CompanyNotificationRecipientsRead(BaseModel):
    id: int
    name: str
    recipients: list[NotificationRecipientRead] = Field(default_factory=list)


class SmtpStatusRead(BaseModel):
    configured: bool
    host: str | None = None
    port: int | None = None
    sender: str | None = None
    username: str | None = None
    use_tls: bool = True
    use_ssl: bool = False
    global_recipient_count: int = 0
    missing: list[str] = Field(default_factory=list)


class EmailSummaryRead(BaseModel):
    id: int
    company_id: int
    company_name: str
    source_id: int
    source_url: str
    discovered_url_id: int
    discovered_url: str
    title: str | None = None
    summary: str
    model: str | None = None
    created_at: datetime
    recipients: list[str] = Field(default_factory=list)
    recipient_count: int = 0
    smtp_configured: bool = False
    would_send: bool = False
    notification_mode: Literal["manual", "automatic"] = "manual"
    email_status: str = "pending"
    email_sent_at: datetime | None = None
    email_error: str | None = None


class MonitorRunWithDiscoveredUrls(MonitorRunRead):
    discovered_urls: list[DiscoveredUrlRead] = Field(default_factory=list)


class StoredUrlRead(BaseModel):
    url: str
    source: Literal["json", "database"]
    first_seen_at: str | None = None
    discovered_at: datetime | None = None
    monitor_run_id: int | None = None
    payload: dict[str, Any] | None = None


class SourceStoredUrlsRead(BaseModel):
    id: int
    company_id: int
    url: str
    strategy: str
    stored_urls: list[StoredUrlRead] = Field(default_factory=list)
    json_url_count: int = 0
    database_url_count: int = 0
    message: str | None = None


class CompanyStoredUrlsRead(BaseModel):
    id: int
    name: str
    sources: list[SourceStoredUrlsRead] = Field(default_factory=list)


class StoredUrlsResponse(BaseModel):
    status: Literal["ok", "warning", "error"]
    message: str | None = None
    companies: list[CompanyStoredUrlsRead] = Field(default_factory=list)


class DiscoveryPreviewUrl(BaseModel):
    url: str
    already_seen: bool = False
    source: str | None = None
    region: str | None = None
    label: str | None = None


class SourceDiscoveryPreviewRead(BaseModel):
    source_id: int
    source_url: str
    strategy: str
    status: Literal["ok", "error"]
    message: str | None = None
    raw_url_count: int = 0
    content_url_count: int = 0
    already_seen_count: int = 0
    new_candidate_count: int = 0
    urls: list[DiscoveryPreviewUrl] = Field(default_factory=list)


class CompanyBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Company name cannot be blank.")
        return value


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Company name cannot be blank.")
        return value


class CompanyRead(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_name: str | None = None
    created_at: datetime
    updated_at: datetime


class SourceBase(BaseModel):
    company_id: int
    url: HttpUrl
    strategy: Literal["parent", "feed", "api"]
    trace_js: bool = False
    js_bundle_sources: list[str] = Field(default_factory=list)
    enabled: bool = True
    schedule_minutes: int = Field(default=60, ge=0)

    @model_validator(mode="after")
    def ignore_trace_js_for_non_parent(self) -> "SourceBase":
        if self.strategy != "parent":
            self.trace_js = False
        return self


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    url: HttpUrl | None = None
    strategy: Literal["parent", "feed", "api"] | None = None
    trace_js: bool | None = None
    js_bundle_sources: list[str] | None = None
    enabled: bool | None = None
    schedule_minutes: int | None = Field(default=None, ge=0)


class SourceRead(SourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SummaryReviewUpdate(BaseModel):
    reviewed: bool = True


class AccountOverviewRead(BaseModel):
    name: str
    role: Literal["customer"]
    company_count: int = 0
    monitor_count: int = 0
    last_login_at: datetime | None = None


class AccountCreate(BaseModel):
    name: str
    password: str


class DailyInsightCountRead(BaseModel):
    date: str
    count: int


class CompanyInsightCountRead(BaseModel):
    company_id: int
    company_name: str
    count: int


class SourceInsightCountRead(BaseModel):
    source_id: int
    url: str
    count: int


class InsightStatsRead(BaseModel):
    days: int
    daily: list[DailyInsightCountRead] = Field(default_factory=list)
    by_company: list[CompanyInsightCountRead] = Field(default_factory=list)
    busiest_sources: list[SourceInsightCountRead] = Field(default_factory=list)
    by_source_daily: dict[int, list[int]] = Field(default_factory=dict)
    avg_seconds_to_insight: float | None = None
