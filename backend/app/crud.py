from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app import models, schemas


EMAIL_NOTIFICATION_MODE_KEY = "email_notification_mode"
VALID_EMAIL_NOTIFICATION_MODES = {"manual", "automatic"}


def get_company(db: Session, company_id: int) -> models.Company | None:
    return db.get(models.Company, company_id)


def list_companies(db: Session) -> list[models.Company]:
    return list(db.scalars(select(models.Company).order_by(models.Company.name)))


def list_companies_with_recipients(db: Session) -> list[models.Company]:
    return list(
        db.scalars(
            select(models.Company)
            .options(selectinload(models.Company.notification_recipients))
            .order_by(models.Company.name)
        )
    )


def create_company(db: Session, company: schemas.CompanyCreate) -> models.Company:
    db_company = models.Company(name=company.name)
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


def get_source(db: Session, source_id: int) -> models.Source | None:
    return db.get(models.Source, source_id)


def list_sources(db: Session) -> list[models.Source]:
    return list(db.scalars(select(models.Source).order_by(models.Source.id)))


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

    return list(db.scalars(query))


def list_monitor_runs(
    db: Session,
    limit: int = 50,
) -> list[models.MonitorRun]:
    return list(
        db.scalars(
            select(models.MonitorRun)
            .order_by(models.MonitorRun.started_at.desc(), models.MonitorRun.id.desc())
            .limit(limit)
        )
    )


def get_monitor_run_with_discovered_urls(
    db: Session,
    run_id: int,
) -> models.MonitorRun | None:
    return db.scalar(
        select(models.MonitorRun)
        .options(selectinload(models.MonitorRun.discovered_urls))
        .where(models.MonitorRun.id == run_id)
    )
