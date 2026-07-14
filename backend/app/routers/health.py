from typing import Any

from fastapi import APIRouter, Request, Response, status

from backend.app.config import get_settings
from backend.app.observability import log_health_event
from backend.app.schemas import DiscoveryHealthRead, HealthCheck


router = APIRouter()


@router.get("/health", response_model=HealthCheck)
def health_check() -> HealthCheck:
    return HealthCheck(status="ok")


@router.get("/health/discovery", response_model=DiscoveryHealthRead)
def discovery_health_check() -> DiscoveryHealthRead:
    settings = get_settings()
    return DiscoveryHealthRead(
        status="ok",
        gemini_configured=bool(settings.google_api_key),
        gemini_model=settings.google_gemini_model,
        zenrows_configured=bool(settings.zenrows_api_key),
        browser_tracing_available=True,
        adapter_cache_path="s3://configured-bucket/environment-scoped/discovery metadata",
        adapter_cache_exists=True,
        cached_adapter_count=0,
        recent_discovery_event_count=0,
        recent_discovery_error_count=0,
        heavy_discovery_lock={},
        limits={"zenrows_timeout_seconds": settings.zenrows_timeout_seconds, "zenrows_max_retries": settings.zenrows_max_retries},
    )


@router.post("/health/events", status_code=status.HTTP_204_NO_CONTENT)
async def record_frontend_health_event(event: dict[str, Any], request: Request) -> Response:
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    metadata = {**metadata, "client_host": request.client.host if request.client else None, "user_agent": request.headers.get("user-agent")}
    raw_duration = event.get("duration_ms")
    log_health_event(
        event_type=str(event.get("event_type") or "frontend_event"),
        service="frontend",
        action=str(event.get("action") or "unknown"),
        status=str(event.get("status") or "ok"),
        duration_ms=float(raw_duration) if isinstance(raw_duration, (int, float)) else None,
        correlation_id=request.headers.get("x-correlation-id"),
        metadata=metadata,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
