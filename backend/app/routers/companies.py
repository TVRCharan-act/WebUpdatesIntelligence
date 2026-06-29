from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app import crud, schemas
from backend.app.database import get_db


router = APIRouter(
    prefix="/companies",
    tags=["companies"],
)

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "",
    response_model=list[schemas.CompanyRead],
)
def list_companies(db: DbSession) -> list[schemas.CompanyRead]:
    return crud.list_companies(db)


@router.get(
    "/{company_id}",
    response_model=schemas.CompanyRead,
)
def get_company(company_id: int, db: DbSession) -> schemas.CompanyRead:
    company = crud.get_company(db, company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found.",
        )
    return company


@router.post(
    "",
    response_model=schemas.CompanyRead,
    status_code=status.HTTP_201_CREATED,
)
def create_company(
    company: schemas.CompanyCreate,
    db: DbSession,
) -> schemas.CompanyRead:
    try:
        return crud.create_company(db, company)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company name already exists.",
        ) from exc


@router.patch(
    "/{company_id}",
    response_model=schemas.CompanyRead,
)
def update_company(
    company_id: int,
    company: schemas.CompanyUpdate,
    db: DbSession,
) -> schemas.CompanyRead:
    db_company = crud.get_company(db, company_id)
    if db_company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found.",
        )

    try:
        return crud.update_company(db, db_company, company)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company name already exists.",
        ) from exc


@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_company(company_id: int, db: DbSession) -> None:
    db_company = crud.get_company(db, company_id)
    if db_company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found.",
        )

    crud.delete_company(db, db_company)
