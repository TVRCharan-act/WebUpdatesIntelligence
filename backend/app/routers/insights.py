from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app import crud, schemas
from backend.app.auth import CurrentUser
from backend.app.database import get_db


router = APIRouter(
    prefix="/insights",
    tags=["insights"],
)

DbSession = Annotated[Session, Depends(get_db)]


def _owner_filter(user: CurrentUser) -> str | None:
    return None if user.role == "admin" else user.name


@router.get("", response_model=list[schemas.SummaryRead])
def list_insights(
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[schemas.SummaryRead]:
    return crud.list_all_summaries(db, limit=limit, owner_name=_owner_filter(user))


@router.get("/stats", response_model=schemas.InsightStatsRead)
def get_insight_stats(
    db: DbSession,
    user: CurrentUser,
    days: Annotated[int, Query(ge=1, le=180)] = 30,
) -> schemas.InsightStatsRead:
    return crud.get_insight_stats(db, owner_name=_owner_filter(user), days=days)


@router.patch("/{summary_id}/review", response_model=schemas.SummaryRead)
def update_insight_review(
    summary_id: int,
    review: schemas.SummaryReviewUpdate,
    db: DbSession,
    user: CurrentUser,
) -> schemas.SummaryRead:
    summary = crud.get_summary(db, summary_id, owner_name=_owner_filter(user))
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insight not found.",
        )

    summary = crud.update_summary_reviewed(db, summary, review.reviewed)
    return schemas.SummaryRead(
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
