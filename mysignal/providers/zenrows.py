"""ZenRows acquisition with bounded asynchronous retries."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from backend.app.config import Settings, get_settings


class AcquisitionError(RuntimeError):
    pass


@dataclass(frozen=True)
class AcquiredPage:
    url: str
    content: str
    content_type: str
    provider: str = "zenrows"


class ZenRowsClient:
    endpoint = "https://api.zenrows.com/v1/"

    def __init__(self, settings: Settings | None = None, *, client: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    async def fetch(self, url: str, *, js_render: bool | None = None) -> AcquiredPage:
        self.settings.require_zenrows()
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise AcquisitionError("httpx is required for ZenRows acquisition.") from exc
        render_javascript = self.settings.zenrows_js_render if js_render is None else js_render
        params = {
            "url": url,
            "apikey": self.settings.zenrows_api_key,
            "js_render": "true" if render_javascript else "false",
        }
        last_error: Exception | None = None
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.settings.zenrows_timeout_seconds, follow_redirects=True)
        try:
            for attempt in range(self.settings.zenrows_max_retries + 1):
                try:
                    response = await client.get(self.endpoint, params=params)
                    response.raise_for_status()
                    content = response.text.strip()
                    if not content:
                        raise AcquisitionError("ZenRows returned an empty response.")
                    return AcquiredPage(
                        url=str(response.url),
                        content=content,
                        content_type=response.headers.get("content-type", "text/html"),
                    )
                except Exception as exc:
                    last_error = exc
                    if attempt >= self.settings.zenrows_max_retries:
                        break
                    await asyncio.sleep(min(2**attempt, 8))
        finally:
            if owns_client:
                await client.aclose()
        raise AcquisitionError(f"ZenRows could not acquire the requested page: {last_error}")
