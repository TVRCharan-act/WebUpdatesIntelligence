from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app import models, schemas


EMAIL_NOTIFICATION_MODE_KEY = "email_notification_mode"
VALID_EMAIL_NOTIFICATION_MODES = {"manual", "automatic"}


def get_company(
    db: Session,
    company_id: int,
    owner_name: str | None = None,
) -> models.Company | None:
    query = select(models.Company).where(models.Company.id == company_id)
    if owner_name is not None:
        query = query.where(models.Company.owner_name == owner_name)
    return db.scalar(query)


def list_companies(db: Session, owner_name: str | None = None) -> list[models.Company]:
    query = select(models.Company).order_by(models.Company.name)
    if owner_name is not None:
        query = query.where(models.Company.owner_name == owner_name)
    return list(db.scalars(query))


def list_companies_with_recipients(
    db: Session,
    owner_name: str | None = None,
) -> list[models.Company]:
    query = (
        select(models.Company)
        .options(selectinload(models.Company.notification_recipients))
        .order_by(models.Company.name)
    )
    if owner_name is not None:
        query = query.where(models.Company.owner_name == owner_name)
    return list(db.scalars(query))


def create_company(
    db: Session,
    company: schemas.CompanyCreate,
    owner_name: str | None = None,
) -> models.Company:
    db_company = models.Company(
        name=company.name,
        owner_name=owner_name,
        priority=company.priority,
    )
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company


def update_company(
    db: Session,
    db_company: models.Company,
    company: schemas.CompanyUpdate,
) -> models.Company:
    db_company.name = company.name
    db.commit()
    db.refresh(db_company)
    return db_company


def delete_company(db: Session, db_company: models.Company) -> None:
    db.delete(db_company)
    db.commit()


def get_notification_recipient(
    db: Session,
    recipient_id: int,
) -> models.NotificationRecipient | None:
    return db.get(models.NotificationRecipient, recipient_id)


def create_notification_recipient(
    db: Session,
    company_id: int,
    recipient: schemas.NotificationRecipientCreate,
) -> models.NotificationRecipient:
    db_recipient = models.NotificationRecipient(
        company_id=company_id,
        email=recipient.email,
        enabled=recipient.enabled,
    )
    db.add(db_recipient)
    db.commit()
    db.refresh(db_recipient)
    return db_recipient


def update_notification_recipient(
    db: Session,
    db_recipient: models.NotificationRecipient,
    recipient: schemas.NotificationRecipientUpdate,
) -> models.NotificationRecipient:
    update_data = recipient.model_dump(exclude_unset=True)

    if "email" in update_data and update_data["email"] is not None:
        db_recipient.email = update_data["email"]

    if "enabled" in update_data and update_data["enabled"] is not None:
        db_recipient.enabled = update_data["enabled"]

    db.commit()
    db.refresh(db_recipient)
    return db_recipient


def delete_notification_recipient(
    db: Session,
    db_recipient: models.NotificationRecipient,
) -> None:
    db.delete(db_recipient)
    db.commit()


def get_email_notification_mode(db: Session) -> str:
    setting = db.get(models.AppSetting, EMAIL_NOTIFICATION_MODE_KEY)
    if setting is None or setting.value not in VALID_EMAIL_NOTIFICATION_MODES:
        return "manual"
    return setting.value


def set_email_notification_mode(db: Session, mode: str) -> str:
    if mode not in VALID_EMAIL_NOTIFICATION_MODES:
        raise ValueError("Unsupported email notification mode.")

    setting = db.get(models.AppSetting, EMAIL_NOTIFICATION_MODE_KEY)
    if setting is None:
        setting = models.AppSetting(
            key=EMAIL_NOTIFICATION_MODE_KEY,
            value=mode,
        )
        db.add(setting)
    else:
        setting.value = mode

    db.commit()
    return mode


def get_source(
    db: Session,
    source_id: int,
    owner_name: str | None = None,
) -> models.Source | None:
    query = select(models.Source).where(models.Source.id == source_id)
    if owner_name is not None:
        query = query.join(models.Source.company).where(models.Company.owner_name == owner_name)
    return db.scalar(query)


def list_sources(db: Session, owner_name: str | None = None) -> list[models.Source]:
    query = select(models.Source).order_by(models.Source.id)
    if owner_name is not None:
        query = query.join(models.Source.company).where(models.Company.owner_name == owner_name)
    return list(db.scalars(query))


def create_source(db: Session, source: schemas.SourceCreate) -> models.Source:
    trace_js = source.trace_js if source.strategy == "parent" else False
    db_source = models.Source(
        company_id=source.company_id,
        url=str(source.url),
        strategy=source.strategy,
        trace_js=trace_js,
        js_bundle_sources=source.js_bundle_sources,
        enabled=source.enabled,
        schedule_minutes=source.schedule_minutes,
    )
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source


def update_source(
    db: Session,
    db_source: models.Source,
    source: schemas.SourceUpdate,
) -> models.Source:
    update_data = source.model_dump(exclude_unset=True)

    if "url" in update_data and update_data["url"] is not None:
        db_source.url = str(update_data["url"])

    if "strategy" in update_data and update_data["strategy"] is not None:
        db_source.strategy = update_data["strategy"]

    if "trace_js" in update_data and update_data["trace_js"] is not None:
        db_source.trace_js = update_data["trace_js"]

    if "enabled" in update_data and update_data["enabled"] is not None:
        db_source.enabled = update_data["enabled"]

    if "schedule_minutes" in update_data and update_data["schedule_minutes"] is not None:
        db_source.schedule_minutes = update_data["schedule_minutes"]

    if "js_bundle_sources" in update_data and update_data["js_bundle_sources"] is not None:
        db_source.js_bundle_sources = update_data["js_bundle_sources"]

    if db_source.strategy != "parent":
        db_source.trace_js = False

    db.commit()
    db.refresh(db_source)
    return db_source


def update_source_js_bundle_sources(
    db: Session,
    db_source: models.Source,
    js_bundle_sources: list[str],
) -> models.Source:
    db_source.js_bundle_sources = js_bundle_sources
    db.commit()
    db.refresh(db_source)
    return db_source


def delete_source(db: Session, db_source: models.Source) -> None:
    db.delete(db_source)
    db.commit()


def list_source_monitor_runs(
    db: Session,
    source_id: int,
    limit: int = 20,
) -> list[models.MonitorRun]:
    return list(
        db.scalars(
            select(models.MonitorRun)
            .where(models.MonitorRun.source_id == source_id)
            .order_by(models.MonitorRun.started_at.desc(), models.MonitorRun.id.desc())
            .limit(limit)
        )
    )


def list_source_discovered_urls(
    db: Session,
    source_id: int,
    limit: int = 50,
) -> list[models.DiscoveredUrl]:
    return list(
        db.scalars(
            select(models.DiscoveredUrl)
            .where(models.DiscoveredUrl.source_id == source_id)
            .order_by(models.DiscoveredUrl.discovered_at.desc(), models.DiscoveredUrl.id.desc())
            .limit(limit)
        )
    )


def list_source_summaries(
    db: Session,
    source_id: int,
    limit: int = 20,
) -> list[schemas.SummaryRead]:
    summaries = list(
        db.scalars(
            select(models.Summary)
            .join(models.Summary.discovered_url)
            .options(selectinload(models.Summary.discovered_url))
            .where(models.DiscoveredUrl.source_id == source_id)
            .order_by(models.Summary.created_at.desc(), models.Summary.id.desc())
            .limit(limit)
        )
    )
    return [
        schemas.SummaryRead(
            id=summary.id,
            discovered_url_id=summary.discovered_url_id,
            discovered_url=summary.discovered_url.url,
            title=summary.title,
            summary=summary.summary,
            model=summary.model,
            severity=summary.severity,
            confidence=summary.confidence,
            reviewed_at=summary.reviewed_at,
            email_status=summary.email_status,
            email_sent_at=summary.email_sent_at,
            email_error=summary.email_error,
            created_at=summary.created_at,
        )
        for summary in summaries
    ]


def get_summary_with_email_context(
    db: Session,
    summary_id: int,
) -> models.Summary | None:
    return db.scalar(
        select(models.Summary)
        .where(models.Summary.id == summary_id)
        .options(
            selectinload(models.Summary.discovered_url)
            .selectinload(models.DiscoveredUrl.source)
            .selectinload(models.Source.company)
            .selectinload(models.Company.notification_recipients)
        )
    )


def list_email_summaries(
    db: Session,
    limit: int = 100,
    company_id: int | None = None,
    owner_name: str | None = None,
) -> list[models.Summary]:
    query = (
        select(models.Summary)
        .join(models.Summary.discovered_url)
        .join(models.DiscoveredUrl.source)
        .join(models.Source.company)
        .options(
            selectinload(models.Summary.discovered_url)
            .selectinload(models.DiscoveredUrl.source)
            .selectinload(models.Source.company)
            .selectinload(models.Company.notification_recipients)
        )
        .order_by(models.Summary.created_at.desc(), models.Summary.id.desc())
        .limit(limit)
    )

    if company_id is not None:
        query = query.where(models.Source.company_id == company_id)
    if owner_name is not None:
        query = query.where(models.Company.owner_name == owner_name)

    return list(db.scalars(query))


def list_monitor_runs(
    db: Session,
    limit: int = 50,
    owner_name: str | None = None,
) -> list[models.MonitorRun]:
    query = (
        select(models.MonitorRun)
        .order_by(models.MonitorRun.started_at.desc(), models.MonitorRun.id.desc())
        .limit(limit)
    )
    if owner_name is not None:
        query = query.join(models.MonitorRun.source).join(models.Source.company).where(
            models.Company.owner_name == owner_name
        )
    return list(db.scalars(query))


def get_monitor_run_with_discovered_urls(
    db: Session,
    run_id: int,
    owner_name: str | None = None,
) -> models.MonitorRun | None:
    query = (
        select(models.MonitorRun)
        .options(selectinload(models.MonitorRun.discovered_urls))
        .where(models.MonitorRun.id == run_id)
    )
    if owner_name is not None:
        query = query.join(models.MonitorRun.source).join(models.Source.company).where(
            models.Company.owner_name == owner_name
        )
    return db.scalar(query)


def list_all_summaries(
    db: Session,
    limit: int = 100,
    owner_name: str | None = None,
) -> list[schemas.SummaryRead]:
    query = (
        select(models.Summary)
        .join(models.Summary.discovered_url)
        .join(models.DiscoveredUrl.source)
        .join(models.Source.company)
        .options(selectinload(models.Summary.discovered_url))
        .order_by(models.Summary.created_at.desc(), models.Summary.id.desc())
        .limit(limit)
    )
    if owner_name is not None:
        query = query.where(models.Company.owner_name == owner_name)

    summaries = list(db.scalars(query))
    return [
        schemas.SummaryRead(
            id=summary.id,
            discovered_url_id=summary.discovered_url_id,
            discovered_url=summary.discovered_url.url,
            title=summary.title,
            summary=summary.summary,
            model=summary.model,
            severity=summary.severity,
            confidence=summary.confidence,
            reviewed_at=summary.reviewed_at,
            email_status=summary.email_status,
            email_sent_at=summary.email_sent_at,
            email_error=summary.email_error,
            created_at=summary.created_at,
        )
        for summary in summaries
    ]


def get_summary(
    db: Session,
    summary_id: int,
    owner_name: str | None = None,
) -> models.Summary | None:
    query = (
        select(models.Summary)
        .join(models.Summary.discovered_url)
        .join(models.DiscoveredUrl.source)
        .join(models.Source.company)
        .where(models.Summary.id == summary_id)
    )
    if owner_name is not None:
        query = query.where(models.Company.owner_name == owner_name)
    return db.scalar(query)


def update_summary_reviewed(
    db: Session,
    summary: models.Summary,
    reviewed: bool,
) -> models.Summary:
    summary.reviewed_at = datetime.now(timezone.utc) if reviewed else None
    db.commit()
    db.refresh(summary)
    return summary


def get_insight_stats(
    db: Session,
    owner_name: str | None = None,
    days: int = 30,
) -> schemas.InsightStatsRead:
    since = datetime.now(timezone.utc) - timedelta(days=days - 1)
    since = since.replace(hour=0, minute=0, second=0, microsecond=0)

    query = (
        select(
            models.Summary.created_at,
            models.DiscoveredUrl.discovered_at,
            models.Source.id.label("source_id"),
            models.Source.url.label("source_url"),
            models.Company.id.label("company_id"),
            models.Company.name.label("company_name"),
        )
        .join(models.Summary.discovered_url)
        .join(models.DiscoveredUrl.source)
        .join(models.Source.company)
        .where(models.Summary.created_at >= since)
    )
    if owner_name is not None:
        query = query.where(models.Company.owner_name == owner_name)

    rows = db.execute(query).all()

    date_range = [(since.date() + timedelta(days=i)).isoformat() for i in range(days)]

    daily_counts: Counter[str] = Counter()
    company_counts: Counter[int] = Counter()
    company_names: dict[int, str] = {}
    source_counts: Counter[int] = Counter()
    source_urls: dict[int, str] = {}
    source_daily: dict[int, Counter[str]] = defaultdict(Counter)
    total_latency_seconds = 0.0
    latency_samples = 0

    for row in rows:
        day = row.created_at.date().isoformat()
        daily_counts[day] += 1
        company_counts[row.company_id] += 1
        company_names[row.company_id] = row.company_name
        source_counts[row.source_id] += 1
        source_urls[row.source_id] = row.source_url
        source_daily[row.source_id][day] += 1

        if row.discovered_at is not None:
            latency = (row.created_at - row.discovered_at).total_seconds()
            if latency >= 0:
                total_latency_seconds += latency
                latency_samples += 1

    daily = [
        schemas.DailyInsightCountRead(date=day, count=daily_counts.get(day, 0))
        for day in date_range
    ]
    by_source_daily = {
        source_id: [counts.get(day, 0) for day in date_range]
        for source_id, counts in source_daily.items()
    }
    by_company = sorted(
        (
            schemas.CompanyInsightCountRead(
                company_id=company_id,
                company_name=company_names[company_id],
                count=count,
            )
            for company_id, count in company_counts.items()
        ),
        key=lambda item: item.count,
        reverse=True,
    )
    busiest_sources = sorted(
        (
            schemas.SourceInsightCountRead(
                source_id=source_id,
                url=source_urls[source_id],
                count=count,
            )
            for source_id, count in source_counts.items()
        ),
        key=lambda item: item.count,
        reverse=True,
    )[:5]

    return schemas.InsightStatsRead(
        days=days,
        daily=daily,
        by_company=by_company,
        busiest_sources=busiest_sources,
        by_source_daily=by_source_daily,
        avg_seconds_to_insight=(
            total_latency_seconds / latency_samples if latency_samples else None
        ),
    )


def account_usage_by_owner(db: Session) -> dict[str, tuple[int, int]]:
    rows = db.execute(
        select(
            models.Company.owner_name,
            func.count(func.distinct(models.Company.id)),
            func.count(models.Source.id),
        )
        .outerjoin(models.Company.sources)
        .where(models.Company.owner_name.isnot(None))
        .group_by(models.Company.owner_name)
    )
    return {
        str(owner): (int(company_count), int(source_count))
        for owner, company_count, source_count in rows
        if owner is not None
    }
