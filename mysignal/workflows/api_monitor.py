from mysignal.discovery.api_discovery import (
    normalize_api_url,
    validate_json_endpoint,
)
from mysignal.discovery.page_links import normalize_page_url
from mysignal.monitoring.inventory_store import (
    load_seen_url_records,
    save_seen_url_records,
)
from mysignal.workflows.parent_monitor import (
    utc_now_iso,
    website_root_for_url,
)


def api_endpoint_content_urls(
    endpoint_url: str,
) -> list[str]:
    normalized_endpoint = normalize_api_url(
        endpoint_url,
    )
    candidate = validate_json_endpoint(
        normalized_endpoint,
        page_url=normalized_endpoint,
        detection_method="tracked-api",
    )

    if candidate is None:
        return []

    return candidate.discovered_urls


def build_api_record(
    *,
    url: str,
    api_url: str,
) -> dict:
    normalized_api_url = normalize_api_url(
        api_url,
    )
    normalized_url = normalize_page_url(
        url,
    )
    root_url = website_root_for_url(
        normalized_api_url,
    )

    return {
        "url": normalized_url,
        "root_url": root_url,
        "api_url": normalized_api_url,
        "source_strategy": "api",
        "trace": [
            root_url,
            normalized_api_url,
            normalized_url,
        ],
        "first_seen_at": utc_now_iso(),
    }


def discover_new_urls_from_apis(
    api_urls: list[str],
    *,
    store_new_urls: bool = True,
) -> tuple[list[str], dict]:
    records = load_seen_url_records()

    new_urls = []
    new_records = {}

    for api_url in api_urls:
        normalized_api_url = normalize_api_url(
            api_url,
        )

        try:
            content_urls = api_endpoint_content_urls(
                normalized_api_url,
            )
        except Exception as exc:
            print(
                f"FAILED TO POLL API: {normalized_api_url}",
            )
            print(
                exc,
            )
            continue

        print()
        print(
            f"API: {normalized_api_url}",
        )
        print(
            f"FOUND API CONTENT URLS: {len(content_urls)}",
        )

        for content_url in content_urls:
            normalized_content_url = normalize_page_url(
                content_url,
            )

            if normalized_content_url in records:
                continue

            if normalized_content_url in new_records:
                continue

            record = build_api_record(
                url=normalized_content_url,
                api_url=normalized_api_url,
            )

            new_urls.append(
                normalized_content_url,
            )
            new_records[
                normalized_content_url
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


def baseline_seen_urls_from_apis(
    api_urls: list[str],
) -> dict:
    records = load_seen_url_records()
    added = {}

    for api_url in api_urls:
        normalized_api_url = normalize_api_url(
            api_url,
        )

        try:
            content_urls = api_endpoint_content_urls(
                normalized_api_url,
            )
        except Exception as exc:
            print(
                f"FAILED TO BASELINE API: {normalized_api_url}",
            )
            print(
                exc,
            )
            continue

        for content_url in content_urls:
            normalized_content_url = normalize_page_url(
                content_url,
            )

            if normalized_content_url in records:
                continue

            record = build_api_record(
                url=normalized_content_url,
                api_url=normalized_api_url,
            )

            records[
                normalized_content_url
            ] = record
            added[
                normalized_content_url
            ] = record

    save_seen_url_records(
        records,
    )

    return added
