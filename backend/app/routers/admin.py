from fastapi import APIRouter, HTTPException, status

from backend.app import auth, schemas
from backend.app.auth import AdminUser, Repository
from backend.app.repository import RecordNotFound
from backend.app.storage import StorageError


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/accounts", response_model=list[schemas.AccountOverviewRead])
def list_accounts(repository: Repository, user: AdminUser) -> list[schemas.AccountOverviewRead]:
    rows: list[schemas.AccountOverviewRead] = []
    for account in auth.configured_accounts(repository):
        if account.role != "customer":
            continue
        companies = repository.list_companies(account.name, limit=10000)
        monitors = repository.list_sources(account.name, limit=10000)
        rows.append(
            schemas.AccountOverviewRead(
                name=account.name,
                role="customer",
                company_count=len(companies),
                monitor_count=len(monitors),
                last_login_at=account.last_login_at,
                default_acquisition_provider=account.default_acquisition_provider,
            )
        )
    return rows


@router.post("/accounts", response_model=schemas.AccountOverviewRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: schemas.AccountCreate, repository: Repository, user: AdminUser) -> schemas.AccountOverviewRead:
    try:
        account = auth.register_account(repository, payload.name, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return schemas.AccountOverviewRead(name=account.name, role="customer", company_count=0, monitor_count=0)


@router.patch("/accounts/{account_name}", response_model=schemas.AccountOverviewRead)
def update_account(
    account_name: str, payload: schemas.AccountSettingsUpdate, repository: Repository, user: AdminUser
) -> schemas.AccountOverviewRead:
    try:
        record = repository.update_account_settings(
            account_name, default_acquisition_provider=payload.default_acquisition_provider
        )
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Customer account not found.") from exc
    companies = repository.list_companies(account_name, limit=10000)
    monitors = repository.list_sources(account_name, limit=10000)
    return schemas.AccountOverviewRead(
        name=str(record["name"]),
        role="customer",
        company_count=len(companies),
        monitor_count=len(monitors),
        last_login_at=record.get("last_login_at"),
        default_acquisition_provider=str(record.get("default_acquisition_provider") or "auto"),
    )


@router.delete("/accounts/{account_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_name: str, repository: Repository, user: AdminUser) -> None:
    try:
        repository.delete_account(account_name)
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Customer account not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Storage refused the deletion. Verify S3 DeleteObject permission for this application's prefix.",
        ) from exc
