from collections import deque
from typing import Iterable, Mapping

from mysignal.discovery.page_links import (
    GLOBAL_REGIONS,
    extract_page_links,
    normalize_page_url,
)
from mysignal.filters.content_filter import is_content_candidate
from mysignal.monitoring.inventory_store import (
    load_global_urls,
    save_global_urls,
)
from mysignal.workflows.global_link_filter import (
    GlobalLinkRules,
    learn_global_urls,
)


DEFAULT_SAMPLE_PAGES_PER_ROOT = 30
DEFAULT_MAX_PAGES_PER_ROOT = 150


def content_links_for_page(
    page_url: str,
    *,
    blocked_urls: set[str] | None = None,
) -> list[str]:
    blocked_urls = blocked_urls or set()

    page_links = extract_page_links(
        page_url,
    )

    return [
        link.url
        for link in page_links.links
        if link.region not in GLOBAL_REGIONS
        and is_content_candidate(
            link.url,
        )
        and link.url not in blocked_urls
    ]


def learn_global_urls_for_root(
    root: str,
    *,
    sample_pages_per_root: int = DEFAULT_SAMPLE_PAGES_PER_ROOT,
    rules: GlobalLinkRules = GlobalLinkRules(),
) -> set[str]:
    normalized_root = normalize_page_url(
        root,
    )

    visited: set[str] = set()
    queue = deque(
        [
            normalized_root,
        ]
    )

    parent_to_urls: dict[str, list[str]] = {}

    while queue and len(
        visited,
    ) < sample_pages_per_root:
        current_url = queue.popleft()

        if current_url in visited:
            continue

        visited.add(
            current_url,
        )

        try:
            urls = content_links_for_page(
                current_url,
            )
        except Exception as exc:
            print(
                f"FAILED TO SAMPLE: {current_url}",
            )
            print(
                exc,
            )
            continue

        parent_to_urls[
            current_url
        ] = urls

        for url in urls:
            if url == normalized_root:
                continue

            if url not in visited and len(
                visited,
            ) + len(
                queue,
            ) < sample_pages_per_root:
                queue.append(
                    url,
                )

    return learn_global_urls(
        parent_to_urls,
        rules=rules,
    )


def load_cached_global_urls_for_root(
    root: str,
) -> set[str]:
    normalized_root = normalize_page_url(
        root,
    )
    global_urls_by_root = load_global_urls()

    return set(
        global_urls_by_root.get(
            normalized_root,
            [],
        )
    )


def save_cached_global_urls_for_root(
    root: str,
    global_urls: set[str],
) -> None:
    normalized_root = normalize_page_url(
        root,
    )
    global_urls_by_root = load_global_urls()

    global_urls_by_root[
        normalized_root
    ] = sorted(
        global_urls,
    )

    save_global_urls(
        global_urls_by_root,
    )


def build_recursive_inventory_for_roots(
    roots: Iterable[str],
    *,
    max_pages_per_root: int = DEFAULT_MAX_PAGES_PER_ROOT,
    sample_pages_per_root: int = DEFAULT_SAMPLE_PAGES_PER_ROOT,
    relearn_global_urls: bool = False,
    global_link_rules: GlobalLinkRules = GlobalLinkRules(),
) -> dict[str, list[str]]:
    inventory: dict[str, list[str]] = {}

    for root in roots:
        normalized_root = normalize_page_url(
            root,
        )

        cached_global_urls = load_cached_global_urls_for_root(
            normalized_root,
        )

        if relearn_global_urls or not cached_global_urls:
            print(
                f"LEARNING GLOBAL URLS: {normalized_root}",
            )

            learned_global_urls = learn_global_urls_for_root(
                normalized_root,
                sample_pages_per_root=sample_pages_per_root,
                rules=global_link_rules,
            )

            cached_global_urls = (
                cached_global_urls
                | learned_global_urls
            )

            save_cached_global_urls_for_root(
                normalized_root,
                cached_global_urls,
            )

        print(
            f"GLOBAL URLS BLOCKED: {len(cached_global_urls)}",
        )

        visited: set[str] = set()
        discovered_content_urls: set[str] = set()

        queue = deque(
            [
                normalized_root,
            ]
        )

        while queue and len(
            visited,
        ) < max_pages_per_root:
            current_url = queue.popleft()

            if current_url in visited:
                continue

            if current_url in cached_global_urls:
                continue

            visited.add(
                current_url,
            )

            try:
                content_urls = content_links_for_page(
                    current_url,
                    blocked_urls=cached_global_urls,
                )
            except Exception as exc:
                print(
                    f"FAILED TO CRAWL: {current_url}",
                )
                print(
                    exc,
                )
                continue

            for url in content_urls:
                if url == normalized_root:
                    continue

                if url in cached_global_urls:
                    continue

                discovered_content_urls.add(
                    url,
                )

                if url not in visited and len(
                    visited,
                ) + len(
                    queue,
                ) < max_pages_per_root:
                    queue.append(
                        url,
                    )

        inventory[
            normalized_root
        ] = sorted(
            discovered_content_urls,
        )

    return inventory


def find_new_recursive_inventory_urls(
    previous_inventory: Mapping[str, Iterable[str]],
    current_inventory: Mapping[str, Iterable[str]],
    roots: Iterable[str],
) -> dict[str, list[str]]:
    changes: dict[str, list[str]] = {}

    for root in roots:
        normalized_root = normalize_page_url(
            root,
        )

        if normalized_root not in previous_inventory:
            continue

        previous_urls = set(
            previous_inventory.get(
                normalized_root,
                [],
            )
        )

        current_urls = set(
            current_inventory.get(
                normalized_root,
                [],
            )
        )

        new_urls = sorted(
            current_urls
            - previous_urls
        )

        if new_urls:
            changes[
                normalized_root
            ] = new_urls

    return changes