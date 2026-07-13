from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from backend.app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    owner_name: Mapped[str | None] = mapped_column(String(255), index=True)
    # Customer-set importance for this tracked company: high | medium | low.
    # Drives sorting in the Insights feed; never inferred by the AI.
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)

    sources: Mapped[list["Source"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    notification_recipients: Mapped[list["NotificationRecipient"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    trace_js: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    js_bundle_sources: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    schedule_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped["Company"] = relationship(back_populates="sources")
    seen_urls: Mapped[list["SeenUrl"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )
    monitor_runs: Mapped[list["MonitorRun"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )
    discovered_urls: Mapped[list["DiscoveredUrl"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )


class SeenUrl(Base):
    __tablename__ = "seen_urls"
    __table_args__ = (
        UniqueConstraint("source_id", "url", name="uq_seen_urls_source_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    source: Mapped["Source"] = relationship(back_populates="seen_urls")


class MonitorRun(Base):
    __tablename__ = "monitor_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)

    source: Mapped["Source"] = relationship(back_populates="monitor_runs")
    discovered_urls: Mapped[list["DiscoveredUrl"]] = relationship(
        back_populates="monitor_run",
    )


class DiscoveredUrl(Base):
    __tablename__ = "discovered_urls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    monitor_run_id: Mapped[int | None] = mapped_column(ForeignKey("monitor_runs.id"))
    url: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    source: Mapped["Source"] = relationship(back_populates="discovered_urls")
    monitor_run: Mapped["MonitorRun | None"] = relationship(back_populates="discovered_urls")
    summaries: Mapped[list["Summary"]] = relationship(
        back_populates="discovered_url",
        cascade="all, delete-orphan",
    )


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    discovered_url_id: Mapped[int] = mapped_column(ForeignKey("discovered_urls.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(50), default="medium", nullable=False)
    confidence: Mapped[str] = mapped_column(String(50), default="medium", nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    discovered_url: Mapped["DiscoveredUrl"] = relationship(back_populates="summaries")


class NotificationRecipient(TimestampMixin, Base):
    __tablename__ = "notification_recipients"
    __table_args__ = (
        UniqueConstraint("company_id", "email", name="uq_notification_recipients_company_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company: Mapped["Company"] = relationship(back_populates="notification_recipients")


class AppSetting(TimestampMixin, Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
