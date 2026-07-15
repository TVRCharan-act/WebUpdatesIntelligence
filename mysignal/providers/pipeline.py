"""Composable acquisition/discovery strategies used by the ECS worker."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from backend.app.config import Settings, get_settings
from mysignal.discovery.api_discovery import normalize_api_url
from mysignal.discovery.page_links import extract_html_links, extract_page_links, normalize_page_url
from mysignal.filters.content_filter import is_content_candidate
from mysignal.providers.zenrows import ZenRowsClient
from mysignal.workflows.api_monitor import api_endpoint_content_urls
from mysignal.workflows.feed_monitor import feed_entry_urls, normalize_feed_url


class PipelineError(RuntimeError):
    pass


@dataclass(frozen=True)
class Candidate:
    url: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class Content:
    url: str
    title: str
    text: str
    provider: str


def _record(source: dict[str, Any], url: str, discovery_provider: str) -> dict[str, Any]:
    source_url = str(source["url"])
    parsed = urlparse(source_url)
    return {
        "url": url,
        "source_strategy": source["strategy"],
        "source_url": source_url,
        "root_url": f"{parsed.scheme}://{parsed.netloc}",
        "trace": [source_url, url],
        "discovery_provider": discovery_provider,
        "first_discovered_at": datetime.now(timezone.utc).isoformat(),
    }


def _run(coroutine):
    try:
        return asyncio.run(coroutine)
    except RuntimeError as exc:
        if "asyncio.run() cannot be called" not in str(exc):
            raise
        raise PipelineError("An async acquisition strategy was invoked from an active event loop.") from exc


def discover_candidates(source: dict[str, Any], settings: Settings | None = None) -> list[Candidate]:
    """Discover without mutating seen state; the repository owns de-duplication."""
    settings = settings or get_settings()
    strategy = str(source["strategy"])
    provider = str(source.get("acquisition_provider") or "auto")
    source_url = str(source["url"])
    if strategy == "feed":
        urls = feed_entry_urls(normalize_feed_url(source_url))
        discovery_provider = "feed"
    elif strategy == "api":
        urls = api_endpoint_content_urls(normalize_api_url(source_url))
        discovery_provider = "api"
    elif strategy == "parent":
        if provider == "zenrows":
            page = _run(ZenRowsClient(settings).fetch(source_url, js_render=bool(source.get("trace_js"))))
            links = extract_html_links(page.content, normalize_page_url(source_url), same_company_only=True)
            urls = [link.url for link in links.values() if is_content_candidate(link.url)]
            discovery_provider = "zenrows"
        else:
            page_links = extract_page_links(normalize_page_url(source_url))
            urls = [link.url for link in page_links.links if is_content_candidate(link.url)]
            discovery_provider = "crawl4ai"
    else:
        raise PipelineError(f"Unsupported monitor strategy: {strategy}")
    unique = sorted({normalize_page_url(url) for url in urls})
    return [Candidate(url=url, payload=_record(source, url, discovery_provider)) for url in unique]


def _content_from_html(url: str, html: str, provider: str) -> Content:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    text = soup.get_text(" ", strip=True)
    if not text:
        raise PipelineError("The acquired page contained no readable content.")
    return Content(url=url, title=title[:500], text=text[:50_000], provider=provider)


DEFAULT_CRAWL4AI_TIMEOUT_SECONDS = 20


async def _crawl4ai_fetch_content_async(url: str, timeout_seconds: float) -> Content:
    from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

    async def crawl_page():
        async with AsyncWebCrawler() as crawler:
            return await crawler.arun(url=url, config=CrawlerRunConfig(cache_mode=CacheMode.DISABLED))

    result = await asyncio.wait_for(crawl_page(), timeout=timeout_seconds)
    if getattr(result, "success", True) is False:
        raise PipelineError(getattr(result, "error_message", None) or "Crawl4AI failed to fetch the page.")
    html = getattr(result, "html", None) or getattr(result, "cleaned_html", None) or ""
    markdown = str(getattr(result, "markdown", None) or "").strip()
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    text = markdown or soup.get_text(" ", strip=True)
    if not text:
        raise PipelineError("Crawl4AI returned no readable content.")
    return Content(url=url, title=title[:500], text=text[:50_000], provider="crawl4ai")


def _crawl4ai_fetch_content(url: str, timeout_seconds: float = DEFAULT_CRAWL4AI_TIMEOUT_SECONDS) -> Content:
    try:
        return _run(_crawl4ai_fetch_content_async(url, timeout_seconds))
    except PipelineError:
        raise
    except Exception as exc:
        raise PipelineError(f"Crawl4AI could not acquire the requested page: {exc}") from exc


def acquire_content(url: str, provider: str, settings: Settings | None = None) -> Content:
    settings = settings or get_settings()
    selected = provider
    if selected == "auto":
        selected = "firecrawl" if settings.firecrawl_api_key else "requests"
    if selected == "zenrows":
        page = _run(ZenRowsClient(settings).fetch(url, js_render=True))
        return _content_from_html(url, page.content, "zenrows")
    if selected == "crawl4ai":
        return _crawl4ai_fetch_content(url)
    if selected == "firecrawl":
        if not settings.firecrawl_api_key:
            raise PipelineError("FIRECRAWL_API_KEY is required when the Firecrawl provider is selected.")
        try:
            from firecrawl import FirecrawlApp
        except ImportError as exc:  # pragma: no cover - optional integration
            raise PipelineError("The optional Firecrawl provider is not installed.") from exc
        result = FirecrawlApp(api_key=settings.firecrawl_api_key).scrape_url(url, formats=["markdown"])
        markdown = result.get("markdown", "") if isinstance(result, dict) else getattr(result, "markdown", "")
        metadata = result.get("metadata", {}) if isinstance(result, dict) else getattr(result, "metadata", {})
        title = metadata.get("title", url) if isinstance(metadata, dict) else getattr(metadata, "title", url)
        if not markdown:
            raise PipelineError("Firecrawl returned no markdown.")
        return Content(url=url, title=str(title)[:500], text=str(markdown)[:50_000], provider="firecrawl")
    if selected != "requests":
        raise PipelineError(f"Unsupported acquisition provider: {selected}")
    response = requests.get(url, timeout=30, headers={"User-Agent": "SentinelActalyst/1.0"})
    response.raise_for_status()
    return _content_from_html(url, response.text, "requests")
