from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app import auth, crud, schemas
from backend.app.auth import AdminUser, configured_accounts
from backend.app.database import get_db


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/accounts", response_model=list[schemas.AccountOverviewRead])
def list_accounts(
    db: DbSession,
    user: AdminUser,
) -> list[schemas.AccountOverviewRead]:
    usage = crud.account_usage_by_owner(db)
    rows: list[schemas.AccountOverviewRead] = []

    for account in configured_accounts():
        if account.role != "customer":
            continue
        company_count, monitor_count = usage.get(account.name, (0, 0))
        rows.append(
            schemas.AccountOverviewRead(
                name=account.name,
                role="customer",
                company_count=company_count,
                monitor_count=monitor_count,
                last_login_at=account.last_login_at,
            )
        )

    return rows


@router.post(
    "/accounts",
    response_model=schemas.AccountOverviewRead,
    status_code=status.HTTP_201_CREATED,
)
def create_account(
    payload: schemas.AccountCreate,
    user: AdminUser,
) -> schemas.AccountOverviewRead:
    try:
        account = auth.register_account(payload.name, payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return schemas.AccountOverviewRead(
        name=account.name,
        role="customer",
        company_count=0,
        monitor_count=0,
        last_login_at=account.last_login_at,
    )
