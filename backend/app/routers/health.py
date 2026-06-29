from typing import Any

from fastapi import APIRouter
from fastapi import Request, Response, status

from backend.app.observability import log_health_event
from backend.app.schemas import HealthCheck


router = APIRouter()


@router.get(
    "/health",
    response_model=HealthCheck,
)
def health_check() -> HealthCheck:
    return HealthCheck(status="ok")


@router.post(
    "/health/events",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def record_frontend_health_event(
    event: dict[str, Any],
    request: Request,
) -> Response:
    metadata = event.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    metadata = {
        **metadata,
        "client_host": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }

    raw_duration = event.get("duration_ms")
    duration_ms = float(raw_duration) if isinstance(raw_duration, (int, float)) else None

    log_health_event(
        event_type=str(event.get("event_type") or "frontend_event"),
        service="frontend",
        action=str(event.get("action") or "unknown"),
        status=str(event.get("status") or "ok"),
        duration_ms=duration_ms,
        metadata=metadata,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
