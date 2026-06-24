from datetime import datetime, timezone
from urllib.parse import urlparse

from mysignal.discovery.page_links import (
    GLOBAL_REGIONS,
    extract_page_links,
    normalize_page_url,
)
from mysignal.filters.content_filter import is_content_candidate
from mysignal.monitoring.inventory_store import (
    load_seen_url_records,
    save_seen_url_records,
)


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


def direct_content_links_for_parent(
    parent_url: str,
) -> list[str]:
    page_links = extract_page_links(
        parent_url,
    )

    urls = []

    for link in page_links.links:
        if link.region in GLOBAL_REGIONS:
            continue

        if not is_content_candidate(
            link.url,
        ):
            continue

        urls.append(
            normalize_page_url(
                link.url,
            )
        )

    return sorted(
        set(
            urls,
        )
    )


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
    parent_urls: list[str],
    *,
    store_new_urls: bool = True,
) -> tuple[list[str], dict]:
    records = load_seen_url_records()

    new_urls = []
    new_records = {}

    for parent_url in parent_urls:
        normalized_parent = normalize_page_url(
            parent_url,
        )

        try:
            child_urls = direct_content_links_for_parent(
                normalized_parent,
            )
        except Exception as exc:
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

    return (
        sorted(
            new_urls,
        ),
        new_records,
    )


def baseline_seen_urls_from_parents(
    parent_urls: list[str],
) -> dict:
    records = load_seen_url_records()
    added = {}

    for parent_url in parent_urls:
        normalized_parent = normalize_page_url(
            parent_url,
        )

        try:
            child_urls = direct_content_links_for_parent(
                normalized_parent,
            )
        except Exception as exc:
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

    return added