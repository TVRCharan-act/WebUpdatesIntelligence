from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from backend.app import schemas
from backend.app.auth import CurrentUser, Repository
from backend.app.repository import RecordNotFound


router = APIRouter(prefix="/insights", tags=["insights"])


def _owner_filter(user: CurrentUser) -> str | None:
    return None if user.role == "admin" else user.name


@router.get("", response_model=list[schemas.SummaryRead])
def list_insights(
    repository: Repository,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict]:
    return repository.list_insights(_owner_filter(user), limit=limit)


@router.get("/stats", response_model=schemas.InsightStatsRead)
def get_insight_stats(
    repository: Repository,
    user: CurrentUser,
    days: Annotated[int, Query(ge=1, le=180)] = 30,
) -> dict:
    return repository.insight_stats(_owner_filter(user), days=days)


@router.patch("/{summary_id}/review", response_model=schemas.SummaryRead)
def update_insight_review(
    summary_id: str,
    review: schemas.SummaryReviewUpdate,
    repository: Repository,
    user: CurrentUser,
) -> dict:
    try:
        return repository.update_insight_review(summary_id, _owner_filter(user), review.reviewed)
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail="Insight not found.") from exc
