from datetime import datetime, timezone
from urllib.parse import urlparse

from mysignal.discovery.advanced_discovery import advanced_discover_content_links
from mysignal.discovery.page_links import (
    extract_page_links,
    normalize_page_url,
)
from mysignal.filters.content_filter import is_content_candidate
from mysignal.monitoring.inventory_store import (
    load_seen_url_records,
    save_seen_url_records,
)
from backend.app.observability import log_health_event


def website_root_for_url(
    url: str,
) -> str:
    parsed = urlparse(
        url,
    )

    return f"{parsed.scheme}://{parsed.netloc}"


def utc_now_iso() -> str:
    return datetime.now(
        timezone.utc,
    ).isoformat()


def parent_url(
    parent,
) -> str:
    url = getattr(
        parent,
        "url",
        parent,
    )

    return str(
        url,
    )


def parent_js_bundle_sources(
    parent,
) -> list[str]:
    sources = getattr(
        parent,
        "js_bundle_sources",
        None,
    )

    if not isinstance(
        sources,
        list,
    ):
        return []

    return [
        str(
            source,
        ).strip()
        for source in sources
        if str(
            source,
        ).strip()
    ]


def parent_trace_js(
    parent,
) -> bool:
    return bool(
        getattr(
            parent,
            "trace_js",
            False,
        )
    )


def all_content_links(
    page_links,
) -> list[str]:
    return sorted(
        {
            normalize_page_url(
                link.url,
            )
            for link in page_links.links
            if is_content_candidate(
                link.url,
            )
        }
    )


def api_content_links_for_parent(
    parent_url: str,
    *,
    js_bundle_sources: list[str] | None = None,
) -> list[str]:
    result = advanced_discover_content_links(
        parent_url,
        script_sources=js_bundle_sources,
    )

    for message in result.log_messages:
        print(
            message,
        )

    return result.urls


def direct_content_links_for_parent(
    parent_url: str,
    *,
    trace_js: bool = False,
    js_bundle_sources: list[str] | None = None,
) -> list[str]:
    page_links = extract_page_links(
        parent_url,
    )

    urls = all_content_links(
        page_links,
    )

    if trace_js:
        urls.extend(
            api_content_links_for_parent(
                parent_url,
                js_bundle_sources=js_bundle_sources,
            )
        )

    deduped_urls = sorted(
        set(
            urls,
        )
    )

    log_health_event(
        event_type="discovery",
        service="celery-worker",
        action="parent_direct_content_links",
        status="ok",
        metadata={
            "parent_url": parent_url,
            "raw_url_count": len(page_links.links),
            "content_url_count": len(deduped_urls),
            "trace_js": trace_js,
        },
    )

    return deduped_urls

def build_trace_record(
    *,
    url: str,
    parent_url: str,
) -> dict:
    normalized_parent = normalize_page_url(
        parent_url,
    )
    root_url = website_root_for_url(
        normalized_parent,
    )

    return {
        "url": normalize_page_url(
            url,
        ),
        "root_url": root_url,
        "parent_url": normalized_parent,
        "trace": [
            root_url,
            normalized_parent,
            normalize_page_url(
                url,
            ),
        ],
        "first_seen_at": utc_now_iso(),
    }


def discover_new_urls_from_parents(
    parent_urls: list,
    *,
    store_new_urls: bool = True,
) -> tuple[list[str], dict]:
    records = load_seen_url_records()

    new_urls = []
    new_records = {}

    crawl_errors = []

    for parent in parent_urls:
        raw_parent_url = parent_url(
            parent,
        )
        trace_js = parent_trace_js(
            parent,
        )
        js_bundle_sources = parent_js_bundle_sources(
            parent,
        )
        normalized_parent = normalize_page_url(
            raw_parent_url,
        )

        try:
            child_urls = direct_content_links_for_parent(
                normalized_parent,
                trace_js=trace_js,
                js_bundle_sources=js_bundle_sources,
            )
        except Exception as exc:
            crawl_errors.append(
                f"{normalized_parent}: {exc}",
            )
            print(
                f"FAILED TO CRAWL PARENT: {normalized_parent}",
            )
            print(
                exc,
            )
            continue

        print()
        print(
            f"PARENT: {normalized_parent}",
        )
        print(
            f"JS TRACE: {'enabled' if trace_js else 'disabled'}",
        )
        print(
            f"FOUND DIRECT CHILD URLS: {len(child_urls)}",
        )

        for child_url in child_urls:
            normalized_child = normalize_page_url(
                child_url,
            )

            if normalized_child in records:
                continue

            if normalized_child in new_records:
                continue

            record = build_trace_record(
                url=normalized_child,
                parent_url=normalized_parent,
            )

            new_urls.append(
                normalized_child,
            )
            new_records[
                normalized_child
            ] = record

    if store_new_urls:
        records.update(
            new_records,
        )

        save_seen_url_records(
            records,
        )

    if crawl_errors and not new_urls:
        raise RuntimeError(
            "Parent crawl failed for all sources: "
            + "; ".join(
                crawl_errors,
            )
        )

    return (
        sorted(
            new_urls,
        ),
        new_records,
    )


def baseline_seen_urls_from_parents(
    parent_urls: list,
) -> dict:
    records = load_seen_url_records()
    added = {}
    crawl_errors = []

    for parent in parent_urls:
        raw_parent_url = parent_url(
            parent,
        )
        trace_js = parent_trace_js(
            parent,
        )
        js_bundle_sources = parent_js_bundle_sources(
            parent,
        )
        normalized_parent = normalize_page_url(
            raw_parent_url,
        )

        try:
            child_urls = direct_content_links_for_parent(
                normalized_parent,
                trace_js=trace_js,
                js_bundle_sources=js_bundle_sources,
            )
        except Exception as exc:
            crawl_errors.append(
                f"{normalized_parent}: {exc}",
            )
            print(
                f"FAILED TO BASELINE PARENT: {normalized_parent}",
            )
            print(
                exc,
            )
            continue

        for child_url in child_urls:
            normalized_child = normalize_page_url(
                child_url,
            )

            if normalized_child in records:
                continue

            record = build_trace_record(
                url=normalized_child,
                parent_url=normalized_parent,
            )

            records[
                normalized_child
            ] = record
            added[
                normalized_child
            ] = record

    save_seen_url_records(
        records,
    )

    if crawl_errors and not added:
        raise RuntimeError(
            "Parent baseline failed for all sources: "
            + "; ".join(
                crawl_errors,
            )
        )

    return added
