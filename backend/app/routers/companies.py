from fastapi import APIRouter, HTTPException, status

from backend.app import schemas
from backend.app.auth import CurrentUser, Repository
from backend.app.repository import DuplicateRecord, RecordNotFound


router = APIRouter(prefix="/companies", tags=["companies"])


def _owner_filter(user: CurrentUser) -> str | None:
    return None if user.role == "admin" else user.name


@router.get("", response_model=list[schemas.CompanyRead])
def list_companies(repository: Repository, user: CurrentUser) -> list[dict]:
    return repository.list_companies(_owner_filter(user))


@router.get("/{company_id}", response_model=schemas.CompanyRead)
def get_company(company_id: int, repository: Repository, user: CurrentUser) -> dict:
    try:
        return repository.get_company(company_id, _owner_filter(user))
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Company not found.") from exc


@router.post("", response_model=schemas.CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(company: schemas.CompanyCreate, repository: Repository, user: CurrentUser) -> dict:
    owner = user.name
    try:
        return repository.create_company(owner, company.name, company.priority)
    except DuplicateRecord as exc:
        raise HTTPException(status_code=409, detail="Company name already exists.") from exc


@router.patch("/{company_id}", response_model=schemas.CompanyRead)
def update_company(company_id: int, company: schemas.CompanyUpdate, repository: Repository, user: CurrentUser) -> dict:
    values = company.model_dump(exclude_none=True)
    if not values:
        raise HTTPException(status_code=400, detail="No company changes were supplied.")
    try:
        return repository.update_company(company_id, _owner_filter(user), **values)
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Company not found.") from exc
    except DuplicateRecord as exc:
        raise HTTPException(status_code=409, detail="Company name already exists.") from exc


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, repository: Repository, user: CurrentUser) -> None:
    try:
        repository.delete_company(company_id, _owner_filter(user))
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Company not found.") from exc
