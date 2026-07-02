from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any


LOG_PATH = Path(os.getenv("APP_HEALTH_LOG_PATH", "logs/app-health.jsonl"))
LOG_MAX_BYTES = int(os.getenv("APP_HEALTH_LOG_MAX_BYTES", "5242880"))
_LOG_LOCK = Lock()


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_json_safe(item) for item in value]
        return repr(value)


def _rotate_log_if_needed() -> None:
    if LOG_MAX_BYTES <= 0 or not LOG_PATH.exists():
        return

    try:
        if LOG_PATH.stat().st_size < LOG_MAX_BYTES:
            return
        archive_path = LOG_PATH.with_name(f"{LOG_PATH.name}.1")
        archive_path.unlink(missing_ok=True)
        LOG_PATH.replace(archive_path)
    except Exception:
        return

def log_health_event(
    *,
    event_type: str,
    service: str,
    action: str,
    status: str = "ok",
    duration_ms: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "service": service,
        "action": action,
        "status": status,
        "duration_ms": round(duration_ms, 3) if duration_ms is not None else None,
        "metadata": _json_safe(metadata or {}),
    }

    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_LOCK:
            _rotate_log_if_needed()
            with LOG_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    except Exception:
        return
