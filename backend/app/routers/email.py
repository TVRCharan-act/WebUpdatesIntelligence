import os
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app import crud, schemas
from backend.app.auth import CurrentUser
from backend.app.database import get_db
from backend.app.observability import log_health_event
from mysignal.models.article import Article
from mysignal.notifications.smtp_email import send_article_update_email


router = APIRouter(
    prefix="/email",
    tags=["email"],
)

DbSession = Annotated[Session, Depends(get_db)]


def _owner_filter(user: CurrentUser) -> str | None:
    return None if user.role == "admin" else user.name


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_recipients(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _smtp_status() -> schemas.SmtpStatusRead:
    email_address = os.getenv("EMAIL_ADDRESS")
    email_app_password = os.getenv("EMAIL_APP_PASSWORD")
    smtp_username = os.getenv("SMTP_USERNAME") or email_address
    smtp_password = os.getenv("SMTP_PASSWORD") or email_app_password
    use_ssl = _env_bool("SMTP_USE_SSL", False)
    host = os.getenv("SMTP_HOST") or (
        "smtp.gmail.com" if email_address and email_app_password else None
    )
    port = int(os.getenv("SMTP_PORT", "465" if use_ssl else "587"))
    sender = os.getenv("SMTP_FROM") or smtp_username
    global_recipients = _split_recipients(
        os.getenv("SMTP_TO") or os.getenv("EMAIL_RECIPIENT")
    )

    missing: list[str] = []
    if not host:
        missing.append("SMTP_HOST or EMAIL_ADDRESS")
    if not sender:
        missing.append("SMTP_FROM or EMAIL_ADDRESS")
    if not smtp_username:
        missing.append("SMTP_USERNAME or EMAIL_ADDRESS")
    if not smtp_password:
        missing.append("SMTP_PASSWORD or EMAIL_APP_PASSWORD")

    return schemas.SmtpStatusRead(
        configured=not missing,
        host=host,
        port=port if host else None,
        sender=sender,
        username=smtp_username,
        use_tls=_env_bool("SMTP_USE_TLS", True),
        use_ssl=use_ssl,
        global_recipient_count=len(global_recipients),
        missing=missing,
    )


@router.get(
    "/smtp-status",
    response_model=schemas.SmtpStatusRead,
)
def get_smtp_status(user: CurrentUser) -> schemas.SmtpStatusRead:
    return _smtp_status()


@router.get(
    "/settings",
    response_model=schemas.EmailNotificationSettingsRead,
)
def get_email_settings(db: DbSession, user: CurrentUser) -> schemas.EmailNotificationSettingsRead:
    return schemas.EmailNotificationSettingsRead(
        mode=crud.get_email_notification_mode(db),
    )


@router.patch(
    "/settings",
    response_model=schemas.EmailNotificationSettingsRead,
)
def update_email_settings(
    settings: schemas.EmailNotificationSettingsUpdate,
    db: DbSession,
    user: CurrentUser,
) -> schemas.EmailNotificationSettingsRead:
    mode = crud.set_email_notification_mode(db, settings.mode)
    return schemas.EmailNotificationSettingsRead(mode=mode)


@router.get(
    "/recipients",
    response_model=list[schemas.CompanyNotificationRecipientsRead],
)
def list_company_recipients(
    db: DbSession,
    user: CurrentUser,
) -> list[schemas.CompanyNotificationRecipientsRead]:
    companies = crud.list_companies_with_recipients(db, owner_name=_owner_filter(user))
    return [
        schemas.CompanyNotificationRecipientsRead(
            id=company.id,
            name=company.name,
            recipients=sorted(
                company.notification_recipients,
                key=lambda recipient: recipient.email,
            ),
        )
        for company in companies
    ]


@router.post(
    "/companies/{company_id}/recipients",
    response_model=schemas.NotificationRecipientRead,
    status_code=status.HTTP_201_CREATED,
)
def create_company_recipient(
    company_id: int,
    recipient: schemas.NotificationRecipientCreate,
    db: DbSession,
    user: CurrentUser,
) -> schemas.NotificationRecipientRead:
    if crud.get_company(db, company_id, owner_name=_owner_filter(user)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found.",
        )

    try:
        return crud.create_notification_recipient(db, company_id, recipient)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recipient already exists for this company.",
        ) from exc


@router.patch(
    "/recipients/{recipient_id}",
    response_model=schemas.NotificationRecipientRead,
)
def update_recipient(
    recipient_id: int,
    recipient: schemas.NotificationRecipientUpdate,
    db: DbSession,
    user: CurrentUser,
) -> schemas.NotificationRecipientRead:
    db_recipient = crud.get_notification_recipient(db, recipient_id)
    if db_recipient is None or crud.get_company(
        db,
        db_recipient.company_id,
        owner_name=_owner_filter(user),
    ) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient not found.",
        )

    try:
        return crud.update_notification_recipient(db, db_recipient, recipient)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recipient already exists for this company.",
        ) from exc


@router.delete(
    "/recipients/{recipient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_recipient(recipient_id: int, db: DbSession, user: CurrentUser) -> None:
    db_recipient = crud.get_notification_recipient(db, recipient_id)
    if db_recipient is None or crud.get_company(
        db,
        db_recipient.company_id,
        owner_name=_owner_filter(user),
    ) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient not found.",
        )

    crud.delete_notification_recipient(db, db_recipient)


@router.get(
    "/summaries",
    response_model=list[schemas.EmailSummaryRead],
)
def list_email_summaries(
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    company_id: int | None = None,
) -> list[schemas.EmailSummaryRead]:
    smtp_configured = _smtp_status().configured
    notification_mode = crud.get_email_notification_mode(db)
    summaries = crud.list_email_summaries(
        db,
        limit=limit,
        company_id=company_id,
        owner_name=_owner_filter(user),
    )

    rows: list[schemas.EmailSummaryRead] = []
    for summary in summaries:
        discovered_url = summary.discovered_url
        source = discovered_url.source
        company = source.company
        recipients = sorted(
            recipient.email
            for recipient in company.notification_recipients
            if recipient.enabled
        )

        rows.append(
            schemas.EmailSummaryRead(
                id=summary.id,
                company_id=company.id,
                company_name=company.name,
                source_id=source.id,
                source_url=source.url,
                discovered_url_id=discovered_url.id,
                discovered_url=discovered_url.url,
                title=summary.title,
                summary=summary.summary,
                model=summary.model,
                created_at=summary.created_at,
                recipients=recipients,
                recipient_count=len(recipients),
                smtp_configured=smtp_configured,
                would_send=(
                    smtp_configured
                    and bool(recipients)
                    and summary.email_status != "sent"
                ),
                notification_mode=notification_mode,
                email_status=summary.email_status,
                email_sent_at=summary.email_sent_at,
                email_error=summary.email_error,
            )
        )

    return rows


@router.post(
    "/summaries/{summary_id}/send",
    response_model=schemas.EmailSendResult,
)
def send_summary_email(
    summary_id: int,
    db: DbSession,
    user: CurrentUser,
) -> schemas.EmailSendResult:
    summary = crud.get_summary_with_email_context(db, summary_id)
    if summary is None or (
        user.role != "admin"
        and summary.discovered_url.source.company.owner_name != user.name
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary not found.",
        )

    discovered_url = summary.discovered_url
    source = discovered_url.source
    company = source.company
    recipients = sorted(
        recipient.email
        for recipient in company.notification_recipients
        if recipient.enabled
    )

    if not recipients:
        summary.email_status = "skipped"
        summary.email_error = "No enabled recipients for this company."
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No enabled recipients for this company.",
        )

    try:
        article = Article(
            url=discovered_url.url,
            title=summary.title or discovered_url.url,
            markdown="",
            summary=summary.summary,
        )
        sent = send_article_update_email(article, recipients=recipients)
    except Exception as exc:
        summary.email_status = "failed"
        summary.email_error = str(exc)
        db.commit()
        log_health_event(
            event_type="email",
            service="backend",
            action="send_summary_email",
            status="error",
            metadata={
                "summary_id": summary.id,
                "url": discovered_url.url,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not sent:
        summary.email_status = "skipped"
        summary.email_error = "SMTP not configured or no recipients."
        db.commit()
        return schemas.EmailSendResult(
            summary_id=summary.id,
            status="skipped",
            message="SMTP not configured or no recipients.",
        )

    summary.email_status = "sent"
    summary.email_sent_at = datetime.now(timezone.utc)
    summary.email_error = None
    db.commit()
    log_health_event(
        event_type="email",
        service="backend",
        action="send_summary_email",
        status="ok",
        metadata={
            "summary_id": summary.id,
            "url": discovered_url.url,
            "recipient_count": len(recipients),
        },
    )
    return schemas.EmailSendResult(
        summary_id=summary.id,
        status="sent",
        message="Email sent.",
    )
