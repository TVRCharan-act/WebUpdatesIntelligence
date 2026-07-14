from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from backend.app import schemas
from backend.app.auth import CurrentUser, Repository
from backend.app.config import get_settings
from backend.app.repository import DuplicateRecord, RecordNotFound
from backend.app.services.monitor_service import send_insight_email
from mysignal.notifications.ses_email import EmailDeliveryError


router = APIRouter(prefix="/email", tags=["email"])


def _owner(user: CurrentUser) -> str:
    # Notification settings are account-scoped. Admins operate their own ops
    # account unless viewing a customer's company-specific records.
    return user.name


def _owner_filter(user: CurrentUser) -> str | None:
    return None if user.role == "admin" else user.name


def _ses_status() -> schemas.SesStatusRead:
    settings = get_settings()
    missing = [] if settings.email_sender else ["SES_FROM_EMAIL"]
    return schemas.SesStatusRead(
        configured=not missing,
        sender=settings.email_sender,
        aws_region=settings.aws_region,
        ses_region=settings.ses_region,
        configuration_set=settings.ses_configuration_set,
        missing=missing,
    )


@router.get("/ses-status", response_model=schemas.SesStatusRead)
def get_ses_status(user: CurrentUser) -> schemas.SesStatusRead:
    return _ses_status()


@router.get("/smtp-status", response_model=schemas.SesStatusRead, include_in_schema=False)
def get_legacy_smtp_status(user: CurrentUser) -> schemas.SesStatusRead:
    return _ses_status()


@router.get("/settings", response_model=schemas.EmailNotificationSettingsRead)
def get_email_settings(repository: Repository, user: CurrentUser) -> schemas.EmailNotificationSettingsRead:
    return schemas.EmailNotificationSettingsRead(mode=repository.get_notification_mode(_owner(user)))


@router.patch("/settings", response_model=schemas.EmailNotificationSettingsRead)
def update_email_settings(settings: schemas.EmailNotificationSettingsUpdate, repository: Repository, user: CurrentUser) -> schemas.EmailNotificationSettingsRead:
    return schemas.EmailNotificationSettingsRead(mode=str(repository.set_notification_mode(_owner(user), settings.mode)["mode"]))


@router.get("/recipients", response_model=list[schemas.CompanyNotificationRecipientsRead])
def list_company_recipients(repository: Repository, user: CurrentUser) -> list[dict]:
    rows = []
    for company in repository.list_companies(_owner_filter(user)):
        owner = str(company["owner_name"])
        rows.append({"id": company["id"], "name": company["name"], "recipients": repository.list_recipients(owner, company_id=int(company["id"]))})
    return rows


@router.post("/companies/{company_id}/recipients", response_model=schemas.NotificationRecipientRead, status_code=status.HTTP_201_CREATED)
def create_company_recipient(company_id: int, recipient: schemas.NotificationRecipientCreate, repository: Repository, user: CurrentUser) -> dict:
    try:
        company = repository.get_company(company_id, _owner_filter(user))
        return repository.create_recipient(str(company["owner_name"]), company_id, recipient.email, recipient.enabled)
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Company not found.") from exc
    except DuplicateRecord as exc:
        raise HTTPException(status_code=409, detail="Recipient already exists for this company.") from exc


@router.patch("/recipients/{recipient_id}", response_model=schemas.NotificationRecipientRead)
def update_recipient(recipient_id: int, recipient: schemas.NotificationRecipientUpdate, repository: Repository, user: CurrentUser) -> dict:
    values = recipient.model_dump(exclude_none=True)
    try:
        return repository.update_recipient(recipient_id, _owner_filter(user), **values)
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Recipient not found.") from exc
    except DuplicateRecord as exc:
        raise HTTPException(status_code=409, detail="Recipient already exists for this company.") from exc


@router.delete("/recipients/{recipient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipient(recipient_id: int, repository: Repository, user: CurrentUser) -> None:
    try:
        repository.delete_recipient(recipient_id, _owner_filter(user))
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Recipient not found.") from exc


@router.get("/summaries", response_model=list[schemas.EmailSummaryRead])
def list_email_summaries(
    repository: Repository,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    company_id: int | None = None,
) -> list[dict]:
    ses = _ses_status()
    rows = []
    for insight in repository.list_insights(_owner_filter(user), limit=limit):
        if company_id is not None and int(insight["company_id"]) != company_id:
            continue
        company = repository.get_company(int(insight["company_id"]), str(insight["owner_name"]))
        source = repository.get_source(int(insight["source_id"]), str(insight["owner_name"]))
        recipients = [item["email"] for item in repository.list_recipients(str(insight["owner_name"]), company_id=int(company["id"])) if item.get("enabled")]
        rows.append({
            **insight,
            "company_name": company["name"],
            "source_url": source["url"],
            "recipients": recipients,
            "recipient_count": len(recipients),
            "ses_configured": ses.configured,
            "would_send": ses.configured and bool(recipients) and insight.get("email_status") != "sent",
            "notification_mode": repository.get_notification_mode(str(insight["owner_name"])),
        })
    return rows


@router.post("/summaries/{summary_id}/send", response_model=schemas.EmailSendResult)
def send_summary_email(summary_id: str, repository: Repository, user: CurrentUser) -> schemas.EmailSendResult:
    try:
        delivery_status, message = send_insight_email(repository, summary_id, _owner_filter(user))
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Summary not found.") from exc
    except EmailDeliveryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return schemas.EmailSendResult(summary_id=summary_id, status=delivery_status, message=message)
