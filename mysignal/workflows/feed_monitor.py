from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import feedparser
import requests

from mysignal.discovery.page_links import normalize_page_url
from mysignal.monitoring.inventory_store import (
    load_seen_url_records,
    save_seen_url_records,
)
from mysignal.workflows.parent_monitor import (
    utc_now_iso,
    website_root_for_url,
)


FEED_USER_AGENT = "mysignal-feed-monitor/1.0"


def normalize_feed_url(
    url: str,
) -> str:
    parsed = urlparse(
        url.strip(),
    )
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip(
        "/",
    )

    normalized = f"{scheme}://{netloc}{path}"

    if parsed.query:
        normalized = f"{normalized}?{parsed.query}"

    return normalized


def _xml_local_name(
    tag: str,
) -> str:
    return tag.rsplit(
        "}",
        1,
    )[-1]


def detect_feed_url(
    url: str,
) -> str | None:
    response = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": FEED_USER_AGENT,
        },
    )
    response.raise_for_status()

    root = ET.fromstring(
        response.content,
    )
    local_name = _xml_local_name(
        root.tag,
    ).lower()

    if local_name == "rss":
        return "rss"

    if local_name == "feed":
        return "atom"

    if local_name == "rdf":
        return "rdf"

    return None


def _entry_url(
    entry,
) -> str | None:
    link = entry.get(
        "link",
    )

    if link:
        return normalize_page_url(
            link,
        )

    for candidate in entry.get(
        "links",
        [],
    ):
        href = candidate.get(
            "href",
        )

        if href:
            return normalize_page_url(
                href,
            )

    identifier = entry.get(
        "id",
    )

    if identifier and urlparse(
        identifier,
    ).scheme in {
        "http",
        "https",
    }:
        return normalize_page_url(
            identifier,
        )

    return None


def feed_entry_urls(
    feed_url: str,
) -> list[str]:
    parsed_feed = feedparser.parse(
        feed_url,
    )

    urls = []

    for entry in parsed_feed.entries:
        url = _entry_url(
            entry,
        )

        if url:
            urls.append(
                url,
            )

    return sorted(
        set(
            urls,
        )
    )


def build_feed_record(
    *,
    url: str,
    feed_url: str,
) -> dict:
    normalized_feed = normalize_feed_url(
        feed_url,
    )
    normalized_url = normalize_page_url(
        url,
    )
    root_url = website_root_for_url(
        normalized_feed,
    )

    return {
        "url": normalized_url,
        "root_url": root_url,
        "feed_url": normalized_feed,
        "source_strategy": "feed",
        "trace": [
            root_url,
            normalized_feed,
            normalized_url,
        ],
        "first_seen_at": utc_now_iso(),
    }


def discover_new_urls_from_feeds(
    feed_urls: list[str],
    *,
    store_new_urls: bool = True,
) -> tuple[list[str], dict]:
    records = load_seen_url_records()

    new_urls = []
    new_records = {}

    for feed_url in feed_urls:
        normalized_feed = normalize_feed_url(
            feed_url,
        )

        try:
            entry_urls = feed_entry_urls(
                normalized_feed,
            )
        except Exception as exc:
            print(
                f"FAILED TO POLL FEED: {normalized_feed}",
            )
            print(
                exc,
            )
            continue

        print()
        print(
            f"FEED: {normalized_feed}",
        )
        print(
            f"FOUND FEED ENTRIES: {len(entry_urls)}",
        )

        for entry_url in entry_urls:
            normalized_entry = normalize_page_url(
                entry_url,
            )

            if normalized_entry in records:
                continue

            if normalized_entry in new_records:
                continue

            record = build_feed_record(
                url=normalized_entry,
                feed_url=normalized_feed,
            )

            new_urls.append(
                normalized_entry,
            )
            new_records[
                normalized_entry
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


def baseline_seen_urls_from_feeds(
    feed_urls: list[str],
) -> dict:
    records = load_seen_url_records()
    added = {}

    for feed_url in feed_urls:
        normalized_feed = normalize_feed_url(
            feed_url,
        )

        try:
            entry_urls = feed_entry_urls(
                normalized_feed,
            )
        except Exception as exc:
            print(
                f"FAILED TO BASELINE FEED: {normalized_feed}",
            )
            print(
                exc,
            )
            continue

        for entry_url in entry_urls:
            normalized_entry = normalize_page_url(
                entry_url,
            )

            if normalized_entry in records:
                continue

            record = build_feed_record(
                url=normalized_entry,
                feed_url=normalized_feed,
            )

            records[
                normalized_entry
            ] = record
            added[
                normalized_entry
            ] = record

    save_seen_url_records(
        records,
    )

    return added
