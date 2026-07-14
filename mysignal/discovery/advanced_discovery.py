from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

from mysignal.discovery.api_discovery import (
    CandidateEndpoint,
    extract_json_urls,
    fetch_text,
    normalize_api_url,
    normalize_endpoint_href,
    normalize_page_url,
    validate_json_endpoint,
    discover_api_endpoints,
)
from mysignal.discovery.page_links import company_domain
from mysignal.filters.content_filter import is_content_candidate
from backend.app.config import get_settings

try:
    from backend.app.observability import LOG_PATH, log_health_event
except Exception:  # pragma: no cover - CLI-only fallback
    LOG_PATH = Path(os.getenv("APP_HEALTH_LOG_PATH", "logs/app-health.jsonl"))
    log_health_event = None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default

    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        return max(minimum, int(raw.strip()))
    except (TypeError, ValueError):
        return default


ADAPTER_CACHE_PATH = Path(
    os.getenv(
        "DISCOVERY_ADAPTER_CACHE_PATH",
        "mysignal/data/discovery_adapters.json",
    )
)
HEAVY_LOCK_PATH = Path(
    os.getenv(
        "DISCOVERY_HEAVY_LOCK_PATH",
        "mysignal/data/discovery_heavy.lock",
    )
)
ADAPTER_VERSION = 1
MAX_EVIDENCE_ENDPOINTS = _env_int("DISCOVERY_MAX_EVIDENCE_ENDPOINTS", 20, minimum=1)
MAX_BROWSER_RESPONSES = _env_int("DISCOVERY_BROWSER_MAX_RESPONSES", 10, minimum=0)
MAX_BROWSER_RESPONSE_CHARS = _env_int("DISCOVERY_BROWSER_RESPONSE_CHARS", 8000, minimum=500)
MAX_BROWSER_SCROLLS = _env_int("DISCOVERY_BROWSER_SCROLLS", 2, minimum=0)
BROWSER_TIMEOUT_MS = _env_int("DISCOVERY_BROWSER_TIMEOUT_MS", 20000, minimum=1000)
BROWSER_SETTLE_MS = _env_int("DISCOVERY_BROWSER_SETTLE_MS", 1000, minimum=0)
MAX_LLM_ENDPOINTS = _env_int("DISCOVERY_MAX_LLM_ENDPOINTS", 12, minimum=1)
MAX_EXECUTED_ENDPOINTS = _env_int("DISCOVERY_MAX_EXECUTED_ENDPOINTS", 20, minimum=1)
MAX_DISCOVERED_URLS = _env_int("DISCOVERY_MAX_DISCOVERED_URLS", 300, minimum=1)
HEAVY_LOCK_TTL_SECONDS = _env_int("DISCOVERY_HEAVY_LOCK_TTL_SECONDS", 900, minimum=30)
ENABLE_BROWSER_TRACING = _env_bool("DISCOVERY_ENABLE_BROWSER", True)
ENABLE_LLM_PLANNER = _env_bool("DISCOVERY_ENABLE_LLM", True)
SKIP_HEAVY_WHEN_CACHED_SUCCESS = _env_bool("DISCOVERY_SKIP_HEAVY_WHEN_CACHED_SUCCESS", True)
REQUEST_USER_AGENT = "Mozilla/5.0 (compatible; MySignalMonitor/1.0)"


@dataclass(frozen=True)
class DiscoveryEndpoint:
    url: str
    method: str = "GET"
    source: str = "llm-planner"


@dataclass
class DiscoveryAdapter:
    domain: str
    version: int = ADAPTER_VERSION
    endpoints: list[DiscoveryEndpoint] = field(default_factory=list)
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class NetworkSample:
    url: str
    status: int | None
    content_type: str
    body: str


@dataclass
class AdvancedDiscoveryResult:
    urls: list[str]
    endpoints: list[str]
    used_cached_adapter: bool = False
    planned_adapter: bool = False
    browser_tracing_status: str = "skipped"
    llm_status: str = "skipped"
    log_messages: list[str] = field(default_factory=list)


class DiscoveryPlannerError(RuntimeError):
    pass


@dataclass
class DiscoveryHeavyLock:
    path: Path = HEAVY_LOCK_PATH
    ttl_seconds: int = HEAVY_LOCK_TTL_SECONDS
    acquired: bool = False
    reason: str | None = None

    def __enter__(self) -> "DiscoveryHeavyLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if self._remove_if_stale():
                return self.__enter__()
            self.reason = "busy"
            return self
        except OSError as exc:
            self.reason = f"unavailable:{type(exc).__name__}"
            return self

        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "created_at": _utc_now(),
                    }
                )
            )
        self.acquired = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self.acquired:
            return
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    def _remove_if_stale(self) -> bool:
        try:
            age = datetime.now(timezone.utc).timestamp() - self.path.stat().st_mtime
        except OSError:
            return False

        if age < self.ttl_seconds:
            return False

        try:
            self.path.unlink(missing_ok=True)
            self.reason = "stale_removed"
            return True
        except OSError:
            return False


def heavy_discovery_lock_status() -> dict[str, Any]:
    if not HEAVY_LOCK_PATH.exists():
        return {"path": str(HEAVY_LOCK_PATH), "locked": False}

    try:
        age_seconds = round(datetime.now(timezone.utc).timestamp() - HEAVY_LOCK_PATH.stat().st_mtime, 3)
    except OSError:
        age_seconds = None

    return {
        "path": str(HEAVY_LOCK_PATH),
        "locked": True,
        "age_seconds": age_seconds,
        "ttl_seconds": HEAVY_LOCK_TTL_SECONDS,
        "stale": age_seconds is not None and age_seconds >= HEAVY_LOCK_TTL_SECONDS,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)


def _log(
    *,
    action: str,
    status: str = "ok",
    started_at: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if not log_health_event:
        return

    log_health_event(
        event_type="discovery",
        service="celery-worker",
        action=action,
        status=status,
        duration_ms=_duration_ms(started_at) if started_at is not None else None,
        metadata=metadata or {},
    )


def _cache_key(page_url: str) -> str:
    return urlparse(page_url).netloc.lower()


def _load_cache() -> dict[str, Any]:
    if not ADAPTER_CACHE_PATH.exists():
        return {}

    try:
        with ADAPTER_CACHE_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def _save_cache(cache: dict[str, Any]) -> None:
    ADAPTER_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ADAPTER_CACHE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(cache, handle, indent=2, sort_keys=True)


def adapter_from_dict(data: dict[str, Any]) -> DiscoveryAdapter | None:
    if not isinstance(data, dict):
        return None

    domain = str(data.get("domain") or "").strip().lower()
    if not domain:
        return None

    endpoints = []
    for item in data.get("endpoints") or []:
        if not isinstance(item, dict):
            continue

        url = str(item.get("url") or "").strip()
        method = str(item.get("method") or "GET").strip().upper()
        source = str(item.get("source") or "llm-planner").strip()

        if not url or method != "GET":
            continue

        endpoints.append(
            DiscoveryEndpoint(
                url=url,
                method=method,
                source=source,
            )
        )

    return DiscoveryAdapter(
        domain=domain,
        version=int(data.get("version") or ADAPTER_VERSION),
        endpoints=endpoints[:MAX_LLM_ENDPOINTS],
        notes=data.get("notes") if isinstance(data.get("notes"), str) else None,
        created_at=data.get("created_at") if isinstance(data.get("created_at"), str) else None,
        updated_at=data.get("updated_at") if isinstance(data.get("updated_at"), str) else None,
    )


def adapter_to_dict(adapter: DiscoveryAdapter) -> dict[str, Any]:
    return {
        "domain": adapter.domain,
        "version": adapter.version,
        "endpoints": [asdict(endpoint) for endpoint in adapter.endpoints],
        "notes": adapter.notes,
        "created_at": adapter.created_at,
        "updated_at": adapter.updated_at,
    }


def load_cached_adapter(page_url: str) -> DiscoveryAdapter | None:
    data = _load_cache().get(
        _cache_key(page_url),
    )
    return adapter_from_dict(data) if isinstance(data, dict) else None


def save_cached_adapter(page_url: str, adapter: DiscoveryAdapter) -> None:
    cache = _load_cache()
    key = _cache_key(page_url)
    current = cache.get(key) if isinstance(cache.get(key), dict) else {}
    created_at = current.get("created_at") if isinstance(current, dict) else None
    adapter.created_at = created_at or _utc_now()
    adapter.updated_at = _utc_now()
    cache[key] = adapter_to_dict(adapter)
    _save_cache(cache)


def _is_allowed_endpoint(
    endpoint_url: str,
    page_url: str,
    observed_domains: set[str],
) -> bool:
    parsed = urlparse(endpoint_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    if company_domain(endpoint_url) == company_domain(page_url):
        return True

    return parsed.netloc.lower() in observed_domains


def _normalize_planned_endpoint(
    raw_url: str,
    page_url: str,
) -> str | None:
    normalized = normalize_endpoint_href(
        raw_url,
        page_url,
    )
    return normalized if normalized else None


def _json_from_sample(sample: NetworkSample) -> Any | None:
    if "json" not in sample.content_type.lower() and ".json" not in sample.url.lower():
        return None

    try:
        return json.loads(sample.body)
    except json.JSONDecodeError:
        return None


def _network_response_is_useful(url: str, content_type: str) -> bool:
    lowered_url = url.lower()
    lowered_type = content_type.lower()
    return (
        "json" in lowered_type
        or "/api/" in lowered_url
        or "graphql" in lowered_url
        or ".json" in lowered_url
    )


def collect_browser_network_samples(page_url: str) -> tuple[list[NetworkSample], str]:
    started_at = perf_counter()
    normalized_url = normalize_page_url(page_url)
    samples: list[NetworkSample] = []

    if MAX_BROWSER_RESPONSES <= 0:
        _log(
            action="browser_network_trace",
            status="skipped",
            started_at=started_at,
            metadata={
                "page_url": normalized_url,
                "reason": "max_browser_responses_zero",
            },
        )
        return samples, "disabled"

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        _log(
            action="browser_network_trace",
            status="skipped",
            started_at=started_at,
            metadata={
                "page_url": normalized_url,
                "reason": "playwright_unavailable",
                "error": str(exc),
            },
        )
        return samples, "unavailable"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=REQUEST_USER_AGENT,
            )

            def handle_response(response):
                if len(samples) >= MAX_BROWSER_RESPONSES:
                    return

                content_type = response.headers.get(
                    "content-type",
                    "",
                )
                if not _network_response_is_useful(response.url, content_type):
                    return

                try:
                    body = response.text()
                except Exception:
                    return

                samples.append(
                    NetworkSample(
                        url=response.url,
                        status=response.status,
                        content_type=content_type,
                        body=body[:MAX_BROWSER_RESPONSE_CHARS],
                    )
                )

            page.on("response", handle_response)
            page.goto(normalized_url, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT_MS)
            page.wait_for_timeout(BROWSER_SETTLE_MS)
            for _ in range(MAX_BROWSER_SCROLLS):
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(750)
            browser.close()
    except Exception as exc:
        _log(
            action="browser_network_trace",
            status="error",
            started_at=started_at,
            metadata={
                "page_url": normalized_url,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "sample_count": len(samples),
            },
        )
        return samples, "error"

    _log(
        action="browser_network_trace",
        status="ok",
        started_at=started_at,
        metadata={
            "page_url": normalized_url,
            "sample_count": len(samples),
        },
    )
    return samples, "ok"


def _sample_summary(sample: NetworkSample) -> dict[str, Any]:
    data = _json_from_sample(sample)
    keys: list[str] = []
    if isinstance(data, dict):
        keys = [str(key) for key in list(data.keys())[:20]]
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        keys = [str(key) for key in list(data[0].keys())[:20]]

    return {
        "url": sample.url,
        "status": sample.status,
        "content_type": sample.content_type,
        "body_preview": sample.body[:1200],
        "top_level_keys": keys,
    }


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(text[start : end + 1])

    if not isinstance(data, dict):
        raise DiscoveryPlannerError("LLM planner did not return a JSON object.")

    return data


def build_planner_evidence(
    *,
    page_url: str,
    deterministic_candidates: list[CandidateEndpoint],
    samples: list[NetworkSample],
) -> dict[str, Any]:
    return {
        "page_url": page_url,
        "root_company": company_domain(page_url),
        "deterministic_endpoints": [
            {
                "endpoint_url": candidate.endpoint_url,
                "content_type": candidate.content_type,
                "detection_method": candidate.detection_method,
                "discovered_url_count": len(candidate.discovered_urls),
                "sample_discovered_urls": candidate.discovered_urls[:10],
            }
            for candidate in deterministic_candidates[:MAX_EVIDENCE_ENDPOINTS]
        ],
        "network_samples": [
            _sample_summary(sample)
            for sample in samples[:MAX_BROWSER_RESPONSES]
        ],
    }


def plan_adapter_with_llm(
    *,
    page_url: str,
    evidence: dict[str, Any],
    observed_domains: set[str],
) -> DiscoveryAdapter | None:
    settings = get_settings()
    if not settings.google_api_key:
        _log(
            action="llm_discovery_planner",
            status="skipped",
            metadata={
                "page_url": page_url,
                "reason": "missing_google_api_key",
            },
        )
        return None

    started_at = perf_counter()
    prompt = f"""
You are generating a deterministic website URL discovery adapter.
Return ONLY valid JSON. Do not include prose.

The adapter must help code find public content URLs from observed page/network evidence.
You may propose GET JSON/API endpoints only. Do not propose POST requests, login, auth, admin, analytics, tracking, asset, image, CSS, JS, font, or unrelated third-party endpoints.
External API domains are allowed only if they appear in observed network samples.

JSON schema:
{{
  "endpoints": [
    {{"url": "https://example.com/api/articles", "method": "GET", "source": "llm-planner"}}
  ],
  "notes": "short reason"
}}

Evidence:
{json.dumps(evidence, ensure_ascii=True)[:24000]}
"""

    try:
        from google import genai
        from google.genai import types

        response = genai.Client(api_key=settings.google_api_key).models.generate_content(
            model=settings.google_gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="Return strict JSON for a deterministic crawler adapter.",
                response_mime_type="application/json",
            ),
        )
        content = response.text or ""
        data = _extract_json_object(content)
    except Exception as exc:
        _log(
            action="llm_discovery_planner",
            status="error",
            started_at=started_at,
            metadata={
                "page_url": page_url,
                "model": settings.google_gemini_model,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )
        return None

    endpoints = []
    for item in data.get("endpoints") or []:
        if not isinstance(item, dict):
            continue

        method = str(item.get("method") or "GET").upper()
        if method != "GET":
            continue

        normalized = _normalize_planned_endpoint(
            str(item.get("url") or ""),
            page_url,
        )
        if not normalized:
            continue

        if not _is_allowed_endpoint(
            normalized,
            page_url,
            observed_domains,
        ):
            continue

        endpoints.append(
            DiscoveryEndpoint(
                url=normalized,
                method="GET",
                source=str(item.get("source") or "llm-planner"),
            )
        )

    adapter = DiscoveryAdapter(
        domain=_cache_key(page_url),
        endpoints=endpoints[:MAX_LLM_ENDPOINTS],
        notes=data.get("notes") if isinstance(data.get("notes"), str) else None,
    )

    _log(
        action="llm_discovery_planner",
        status="ok",
        started_at=started_at,
        metadata={
            "page_url": page_url,
            "model": settings.google_gemini_model,
            "planned_endpoint_count": len(adapter.endpoints),
        },
    )
    return adapter if adapter.endpoints else None


def _urls_from_network_samples(
    page_url: str,
    samples: list[NetworkSample],
) -> list[str]:
    urls: list[str] = []
    root_company = company_domain(page_url)

    for sample in samples:
        data = _json_from_sample(sample)
        if data is None:
            continue

        urls.extend(
            extract_json_urls(
                data,
                page_url=page_url,
                root_company=root_company,
            )
        )

    return sorted(set(urls))[:MAX_DISCOVERED_URLS]


def execute_adapter(
    *,
    page_url: str,
    adapter: DiscoveryAdapter,
    observed_domains: set[str],
) -> list[CandidateEndpoint]:
    started_at = perf_counter()
    candidates: list[CandidateEndpoint] = []

    for endpoint in adapter.endpoints[:MAX_EXECUTED_ENDPOINTS]:
        if endpoint.method != "GET":
            continue

        if not _is_allowed_endpoint(
            endpoint.url,
            page_url,
            observed_domains,
        ):
            continue

        candidate = validate_json_endpoint(
            endpoint.url,
            page_url=page_url,
            detection_method=endpoint.source,
        )
        if candidate and candidate.discovered_urls:
            candidates.append(
                candidate,
            )

    _log(
        action="execute_discovery_adapter",
        status="ok",
        started_at=started_at,
        metadata={
            "page_url": page_url,
            "adapter_domain": adapter.domain,
            "endpoint_count": len(adapter.endpoints),
            "accepted_endpoint_count": len(candidates),
            "discovered_url_count": sum(len(candidate.discovered_urls) for candidate in candidates),
        },
    )
    return candidates


def discovery_limit_summary() -> dict[str, Any]:
    return {
        "enable_browser": ENABLE_BROWSER_TRACING,
        "enable_llm": ENABLE_LLM_PLANNER,
        "skip_heavy_when_cached_success": SKIP_HEAVY_WHEN_CACHED_SUCCESS,
        "max_evidence_endpoints": MAX_EVIDENCE_ENDPOINTS,
        "max_browser_responses": MAX_BROWSER_RESPONSES,
        "max_browser_response_chars": MAX_BROWSER_RESPONSE_CHARS,
        "max_browser_scrolls": MAX_BROWSER_SCROLLS,
        "browser_timeout_ms": BROWSER_TIMEOUT_MS,
        "browser_settle_ms": BROWSER_SETTLE_MS,
        "max_llm_endpoints": MAX_LLM_ENDPOINTS,
        "max_executed_endpoints": MAX_EXECUTED_ENDPOINTS,
        "max_discovered_urls": MAX_DISCOVERED_URLS,
        "heavy_lock_ttl_seconds": HEAVY_LOCK_TTL_SECONDS,
    }


def advanced_discover_content_links(
    page_url: str,
    *,
    script_sources: list[str] | None = None,
    use_llm: bool = True,
    use_browser: bool = True,
) -> AdvancedDiscoveryResult:
    started_at = perf_counter()
    normalized_url = normalize_page_url(page_url)
    result = AdvancedDiscoveryResult(urls=[], endpoints=[])
    effective_use_browser = use_browser and ENABLE_BROWSER_TRACING
    effective_use_llm = use_llm and ENABLE_LLM_PLANNER

    deterministic_candidates = discover_api_endpoints(
        normalized_url,
        script_sources=script_sources,
    )
    for candidate in deterministic_candidates:
        result.urls.extend(candidate.discovered_urls)
        result.endpoints.append(candidate.endpoint_url)

    observed_domains = {
        urlparse(normalized_url).netloc.lower(),
    }
    samples: list[NetworkSample] = []

    adapter = load_cached_adapter(
        normalized_url,
    )
    cached_url_count = 0
    if adapter:
        result.used_cached_adapter = True
        adapter_candidates = execute_adapter(
            page_url=normalized_url,
            adapter=adapter,
            observed_domains=observed_domains,
        )
        for candidate in adapter_candidates:
            result.urls.extend(candidate.discovered_urls)
            result.endpoints.append(candidate.endpoint_url)
            cached_url_count += len(candidate.discovered_urls)

    deterministic_url_count = sum(len(candidate.discovered_urls) for candidate in deterministic_candidates)
    cached_success = cached_url_count > 0
    heavy_skipped_reason: str | None = None

    if cached_success and SKIP_HEAVY_WHEN_CACHED_SUCCESS:
        heavy_skipped_reason = "cached_adapter_success"
        result.browser_tracing_status = "cached-skip" if effective_use_browser else "disabled"
        result.llm_status = "cached-only" if effective_use_llm else "disabled"
    elif not effective_use_browser and not effective_use_llm:
        heavy_skipped_reason = "disabled"
        result.browser_tracing_status = "disabled"
        result.llm_status = "disabled"
    else:
        with DiscoveryHeavyLock() as heavy_lock:
            if not heavy_lock.acquired:
                heavy_skipped_reason = heavy_lock.reason or "busy"
                result.browser_tracing_status = "locked" if effective_use_browser else "disabled"
                result.llm_status = "locked" if effective_use_llm else "disabled"
                _log(
                    action="heavy_discovery_lock",
                    status="skipped",
                    metadata={
                        "page_url": normalized_url,
                        "reason": heavy_skipped_reason,
                        "lock": heavy_discovery_lock_status(),
                    },
                )
            else:
                _log(
                    action="heavy_discovery_lock",
                    status="ok",
                    metadata={
                        "page_url": normalized_url,
                        "lock_path": str(HEAVY_LOCK_PATH),
                    },
                )

                if effective_use_browser:
                    samples, result.browser_tracing_status = collect_browser_network_samples(
                        normalized_url,
                    )
                    result.urls.extend(
                        _urls_from_network_samples(
                            normalized_url,
                            samples,
                        )
                    )
                    observed_domains.update(
                        urlparse(sample.url).netloc.lower()
                        for sample in samples
                        if urlparse(sample.url).netloc
                    )
                else:
                    result.browser_tracing_status = "disabled"

                should_plan = effective_use_llm and (
                    not adapter
                    or bool(samples)
                    or not cached_success
                )
                if should_plan:
                    evidence = build_planner_evidence(
                        page_url=normalized_url,
                        deterministic_candidates=deterministic_candidates,
                        samples=samples,
                    )
                    planned = plan_adapter_with_llm(
                        page_url=normalized_url,
                        evidence=evidence,
                        observed_domains=observed_domains,
                    )
                    if planned:
                        result.planned_adapter = True
                        result.llm_status = "ok"
                        save_cached_adapter(
                            normalized_url,
                            planned,
                        )
                        planned_candidates = execute_adapter(
                            page_url=normalized_url,
                            adapter=planned,
                            observed_domains=observed_domains,
                        )
                        for candidate in planned_candidates:
                            result.urls.extend(candidate.discovered_urls)
                            result.endpoints.append(candidate.endpoint_url)
                    else:
                        result.llm_status = "no-plan"
                elif not use_llm or not ENABLE_LLM_PLANNER:
                    result.llm_status = "disabled"
                else:
                    result.llm_status = "cached-only"

    result.urls = sorted(
        {
            normalize_page_url(url)
            for url in result.urls
            if is_content_candidate(url)
        }
    )[:MAX_DISCOVERED_URLS]
    result.endpoints = sorted(set(result.endpoints))[:MAX_EXECUTED_ENDPOINTS]
    result.log_messages = [
        (
            "Advanced discovery: "
            f"deterministic endpoints={len(deterministic_candidates)}, "
            f"deterministic_urls={deterministic_url_count}, "
            f"browser={result.browser_tracing_status}, "
            f"cached_adapter={result.used_cached_adapter}, "
            f"cached_urls={cached_url_count}, "
            f"llm={result.llm_status}."
        ),
        f"Advanced discovery accepted {len(result.urls)} URL(s) from {len(result.endpoints)} endpoint(s).",
    ]
    if heavy_skipped_reason:
        result.log_messages.append(
            f"Advanced discovery heavy path skipped: {heavy_skipped_reason}."
        )

    _log(
        action="advanced_content_links",
        status="ok",
        started_at=started_at,
        metadata={
            "page_url": normalized_url,
            "url_count": len(result.urls),
            "endpoint_count": len(result.endpoints),
            "browser_tracing_status": result.browser_tracing_status,
            "llm_status": result.llm_status,
            "used_cached_adapter": result.used_cached_adapter,
            "planned_adapter": result.planned_adapter,
            "heavy_skipped_reason": heavy_skipped_reason,
            "limits": discovery_limit_summary(),
        },
    )
    return result

def discovery_health_summary() -> dict[str, Any]:
    cache = _load_cache()
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        browser_available = True
    except Exception:
        browser_available = False

    recent_events = 0
    recent_errors = 0
    try:
        if LOG_PATH.exists():
            lines = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()[-300:]
            for line in lines:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("event_type") != "discovery":
                    continue
                recent_events += 1
                if event.get("status") == "error":
                    recent_errors += 1
    except Exception:
        pass

    return {
        "status": "ok",
        "gemini_configured": bool(get_settings().google_api_key),
        "gemini_model": get_settings().google_gemini_model,
        "zenrows_configured": bool(get_settings().zenrows_api_key),
        "browser_tracing_available": browser_available,
        "adapter_cache_path": str(ADAPTER_CACHE_PATH),
        "adapter_cache_exists": ADAPTER_CACHE_PATH.exists(),
        "cached_adapter_count": len(cache),
        "recent_discovery_event_count": recent_events,
        "recent_discovery_error_count": recent_errors,
        "heavy_discovery_lock": heavy_discovery_lock_status(),
        "limits": discovery_limit_summary(),
    }
