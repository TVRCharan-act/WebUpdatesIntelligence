import argparse
from pathlib import Path
import sys
from urllib.parse import urlparse


ROOT_DIR = Path(
    __file__,
).resolve().parents[1]

if str(
    ROOT_DIR,
) not in sys.path:
    sys.path.insert(
        0,
        str(
            ROOT_DIR,
        ),
    )

from mysignal.discovery.api_discovery import (
    CandidateEndpoint,
    discover_api_endpoints,
    normalize_api_url,
)
from mysignal.discovery.page_links import (
    GLOBAL_REGIONS,
    DiscoveredLink,
    PageLinks,
    extract_page_links,
    normalize_page_url,
)
from mysignal.monitoring.inventory_store import (
    TrackedRecursiveRoot,
    load_tracked_recursive_targets,
    save_tracked_recursive_targets,
)
from mysignal.filters.content_filter import is_content_candidate
from mysignal.workflows.api_monitor import (
    baseline_seen_urls_from_apis,
)
from mysignal.workflows.feed_monitor import (
    baseline_seen_urls_from_feeds,
    detect_feed_url,
    normalize_feed_url,
)


REGION_GROUPS = [
    (
        "NAVIGATION",
        {
            "nav",
        },
    ),
    (
        "SIDEBAR",
        {
            "sidebar",
        },
    ),
    (
        "FOOTER",
        {
            "footer",
        },
    ),
    (
        "MAIN CONTENT",
        {
            "main",
        },
    ),
    (
        "OTHER PAGE LINKS",
        {
            "other",
        },
    ),
]
MIN_HTML_CONTENT_URLS = 2
MIN_API_CONTENT_URLS = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactively explore a site by page link origin.",
    )
    parser.add_argument(
        "website",
        help="Website URL to start exploring.",
    )
    parser.add_argument(
        "--max-links",
        type=int,
        default=100,
        help="Maximum links to print per page.",
    )
    parser.add_argument(
        "--same-company-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Keep only URLs on the same company/domain.",
    )
    parser.add_argument(
        "--js-bundle-source",
        action="append",
        default=[],
        help=(
            "Optional same-origin JavaScript bundle URL/path to analyze. "
            "Can be repeated. Relative paths are resolved from the explored page."
        ),
    )
    parser.add_argument(
        "--trace-js",
        action="store_true",
        default=False,
        help="Opt in to JavaScript bundle/API endpoint discovery during exploration.",
    )
    return parser.parse_args()


def display_label(
    link: DiscoveredLink,
) -> str:
    path = urlparse(
        link.url,
    ).path or "/"

    if link.label:
        return f"{path} ({link.label})"

    return path


def links_for_display(
    links: list[DiscoveredLink],
    *,
    include_global_regions: bool,
    max_links: int,
) -> list[DiscoveredLink]:
    filtered_links = [
        link
        for link in links
        if include_global_regions or link.region not in GLOBAL_REGIONS
    ]

    return filtered_links[
        :max_links
    ]


def print_path(
    path: list[str],
) -> None:
    print()
    print("CURRENT PATH")
    print("=" * 80)

    for index, url in enumerate(
        path,
    ):
        prefix = "-> " if index else ""
        indent = "   " * index
        print(
            f"{indent}{prefix}{url}",
        )


def print_links(
    links: list[DiscoveredLink],
) -> None:
    print()
    print("LINKS FOUND ON THIS PAGE")
    print("=" * 80)

    link_index = 1

    for group_name, group_regions in REGION_GROUPS:
        group_links = [
            link
            for link in links
            if link.region in group_regions
        ]

        if not group_links:
            continue

        print()
        print(
            group_name,
        )
        print("-" * 40)

        for link in group_links:
            print(
                f"{link_index}. [{link.region}] {display_label(link)} - {link.url}",
            )
            link_index += 1


def choose_link(
    value: str,
    links: list[DiscoveredLink],
) -> str | None:
    value = value.strip()

    if not value:
        return None

    if value.isdigit():
        index = int(
            value,
        ) - 1

        if 0 <= index < len(
            links,
        ):
            return links[
                index
            ].url

        print(
            f"Selection out of range: {value}",
        )
        return None

    return normalize_page_url(
        value,
    )


def print_tracked_roots() -> None:
    tracked_roots = load_tracked_recursive_targets()

    print()
    print("TRACKED SOURCES")
    print("=" * 60)

    if not tracked_roots:
        print(
            "None",
        )
        return

    for index, root in enumerate(
        tracked_roots,
        start=1,
    ):
        recipients = (
            ", ".join(
                root.recipients,
            )
            if root.recipients
            else "default SMTP recipients"
        )
        bundle_text = (
            f" [{len(root.js_bundle_sources)} JS bundle(s)]"
            if root.js_bundle_sources
            else ""
        )
        trace_text = " [JS trace]" if root.trace_js else ""
        print(
            f"{index}. [{root.strategy}]{trace_text}{bundle_text} {root.url} -> {recipients}",
        )


def split_recipients(
    value: str,
) -> list[str]:
    return [
        recipient.strip()
        for recipient in value.split(
            ",",
        )
        if recipient.strip()
    ]


def track_root(
    selected_url: str,
    *,
    trace_js: bool = False,
    js_bundle_sources: list[str] | None = None,
) -> None:
    js_bundle_sources = (
        [
            source.strip()
            for source in js_bundle_sources
            if source.strip()
        ]
        if js_bundle_sources
        else None
    )
    tracked_roots = load_tracked_recursive_targets()
    existing_urls = [
        root.url
        for root in tracked_roots
    ]

    if selected_url not in existing_urls:
        recipients = split_recipients(
            input(
                "Alert recipients for this URL (comma separated, blank for default SMTP recipients): ",
            )
        )
        tracked_roots.append(
            TrackedRecursiveRoot(
                url=selected_url,
                recipients=recipients,
                strategy="parent",
                trace_js=trace_js,
                js_bundle_sources=js_bundle_sources,
            )
        )
        save_tracked_recursive_targets(
            tracked_roots,
        )
        print(
            f"Tracking recursively: {selected_url}",
        )
        return

    if trace_js or js_bundle_sources:
        updated_roots = [
            (
                TrackedRecursiveRoot(
                    url=root.url,
                    recipients=root.recipients,
                    strategy=root.strategy,
                    trace_js=root.trace_js or trace_js,
                    js_bundle_sources=js_bundle_sources
                    if js_bundle_sources is not None
                    else root.js_bundle_sources,
                )
                if root.url == selected_url
                else root
            )
            for root in tracked_roots
        ]
        save_tracked_recursive_targets(
            updated_roots,
        )
        print(
            f"Updated tracking preferences for: {selected_url}",
        )
        return

    print(
        f"Already tracking: {selected_url}",
    )


def track_feed_source(
    feed_url: str,
    feed_kind: str,
) -> None:
    tracked_sources = load_tracked_recursive_targets()
    existing_urls = [
        root.url
        for root in tracked_sources
    ]

    if feed_url in existing_urls:
        print(
            f"Already tracking feed: {feed_url}",
        )
        return

    recipients = split_recipients(
        input(
            "Alert recipients for this feed (comma separated, blank for default SMTP recipients): ",
        )
    )
    tracked_sources.append(
        TrackedRecursiveRoot(
            url=feed_url,
            recipients=recipients,
            strategy="feed",
        )
    )
    save_tracked_recursive_targets(
        tracked_sources,
    )

    added = baseline_seen_urls_from_feeds(
        [
            feed_url,
        ]
    )

    print()
    print(
        f"Detected {feed_kind.upper()} feed.",
    )
    print(
        f"Tracking feed: {feed_url}",
    )
    print(
        f"Baseline entries marked as seen: {len(added)}",
    )


def track_api_source(
    endpoint_url: str,
) -> None:
    tracked_sources = load_tracked_recursive_targets()
    existing_urls = [
        root.url
        for root in tracked_sources
    ]

    if endpoint_url in existing_urls:
        print(
            f"Already tracking API: {endpoint_url}",
        )
        return

    recipients = split_recipients(
        input(
            "Alert recipients for this API (comma separated, blank for default SMTP recipients): ",
        )
    )
    tracked_sources.append(
        TrackedRecursiveRoot(
            url=endpoint_url,
            recipients=recipients,
            strategy="api",
        )
    )
    save_tracked_recursive_targets(
        tracked_sources,
    )

    added = baseline_seen_urls_from_apis(
        [
            endpoint_url,
        ]
    )

    print()
    print(
        "Tracking API endpoint.",
    )
    print(
        f"API: {endpoint_url}",
    )
    print(
        f"Baseline entries marked as seen: {len(added)}",
    )


def content_links_from_discovered(
    links: list[DiscoveredLink],
) -> list[str]:
    return sorted(
        {
            normalize_page_url(
                link.url,
            )
            for link in links
            if link.region not in GLOBAL_REGIONS
            and link.source in {
                "link",
                "markdown",
            }
            and is_content_candidate(
                link.url,
            )
        }
    )


def print_candidate_endpoints(
    candidates: list[CandidateEndpoint],
) -> None:
    print()
    print("JSON ENDPOINT CANDIDATES")
    print("=" * 80)

    for index, candidate in enumerate(
        candidates[:5],
        start=1,
    ):
        print()
        print(
            f"{index}. score={candidate.score} method={candidate.detection_method}",
        )
        print(
            candidate.endpoint_url,
        )

        for url in candidate.discovered_urls[:5]:
            print(
                f"   - {url}",
            )


def prompt_for_api_tracking(
    candidates: list[CandidateEndpoint],
) -> bool:
    if not candidates:
        return False

    print_candidate_endpoints(
        candidates,
    )
    print()
    value = input(
        "Track a JSON endpoint directly? Enter number, y for top candidate, or press Enter to skip: ",
    ).strip().lower()

    if not value or value in {
        "n",
        "no",
    }:
        return False

    if value == "y":
        candidate_index = 0
    elif value.isdigit():
        candidate_index = int(
            value,
        ) - 1
    else:
        print(
            f"Invalid API selection: {value}",
        )
        return False

    if not 0 <= candidate_index < len(
        candidates,
    ):
        print(
            f"API selection out of range: {value}",
        )
        return False

    best_candidate = candidates[
        candidate_index
    ]

    if best_candidate.score < MIN_API_CONTENT_URLS:
        print(
            f"Warning: selected endpoint has a low content score ({best_candidate.score}).",
        )

    track_api_source(
        best_candidate.endpoint_url,
    )
    return True


def discover_dynamic_content_sources(
    page_url: str,
    *,
    js_bundle_sources: list[str] | None = None,
) -> list[CandidateEndpoint]:
    candidates = discover_api_endpoints(
        page_url,
        script_sources=js_bundle_sources,
    )

    if candidates:
        return candidates

    return []


def links_from_candidate_endpoints(
    candidates: list[CandidateEndpoint],
    *,
    source_page: str,
) -> list[DiscoveredLink]:
    links = []
    seen_urls = set()

    for candidate in candidates:
        for url in candidate.discovered_urls:
            normalized_url = normalize_page_url(
                url,
            )

            if normalized_url in seen_urls:
                continue

            links.append(
                DiscoveredLink(
                    url=normalized_url,
                    source_page=source_page,
                    region="main",
                    label=f"API: {candidate.endpoint_url}",
                    source="api-discovery",
                )
            )
            seen_urls.add(
                normalized_url,
            )

    return links


def merge_discovered_links(
    page_links: PageLinks,
    extra_links: list[DiscoveredLink],
) -> PageLinks:
    links_by_url = {
        link.url: link
        for link in page_links.links
    }

    for link in extra_links:
        links_by_url.setdefault(
            link.url,
            link,
        )

    return PageLinks(
        page_url=page_links.page_url,
        links=sorted(
            links_by_url.values(),
            key=lambda link: (
                link.region,
                link.url,
            ),
        ),
    )


def remove_tracked_root() -> None:
    tracked_roots = load_tracked_recursive_targets()

    if not tracked_roots:
        print(
            "No tracked sources to remove.",
        )
        return

    print_tracked_roots()
    value = input(
        "Enter tracked root number or full URL to remove: ",
    ).strip()

    if not value:
        return

    remove_url = None

    if value.isdigit():
        index = int(
            value,
        ) - 1

        if 0 <= index < len(
            tracked_roots,
        ):
            remove_url = tracked_roots[
                index
            ].url
    else:
        normalized_value = normalize_page_url(
            value,
        )
        normalized_feed_value = normalize_feed_url(
            value,
        )
        normalized_api_value = normalize_api_url(
            value,
        )

        for root in tracked_roots:
            normalized_root = (
                normalize_feed_url(
                    root.url,
                )
                if root.strategy == "feed"
                else normalize_api_url(
                    root.url,
                )
                if root.strategy == "api"
                else normalize_page_url(
                    root.url,
                )
            )

            if normalized_root in {
                normalized_value,
                normalized_feed_value,
                normalized_api_value,
            }:
                remove_url = root.url
                break

    remaining_roots = [
        root
        for root in tracked_roots
        if root.url != remove_url
    ]

    if not remove_url or len(
        remaining_roots,
    ) == len(
        tracked_roots,
    ):
        print(
            "Tracked root not found.",
        )
        return

    save_tracked_recursive_targets(
        remaining_roots,
    )
    print(
        f"Removed: {remove_url}",
    )


def selected_url_menu(
    selected_url: str,
) -> str:
    print()
    print(
        f"Selected: {selected_url}",
    )
    print("Options:")
    print("  e = explore this URL")
    print("  t = track this URL recursively")
    print("  o = print URL")
    print("  c = cancel")

    return input(
        "Choose option: ",
    ).strip().lower()


def main() -> None:
    args = parse_args()
    js_bundle_sources = [
        source.strip()
        for source in args.js_bundle_source
        if source.strip()
    ]
    feed_kind = None

    try:
        feed_kind = detect_feed_url(
            args.website,
        )
    except Exception:
        feed_kind = None

    if feed_kind:
        track_feed_source(
            normalize_feed_url(
                args.website,
            ),
            feed_kind,
        )
        return

    current_url = normalize_page_url(
        args.website,
    )
    history: list[str] = []
    path: list[str] = [
        current_url,
    ]
    api_checked_urls: set[str] = set()

    while True:
        try:
            page_links = extract_page_links(
                current_url,
                same_company_only=args.same_company_only,
            )
        except Exception as exc:
            print(
                f"Failed to fetch {current_url}",
            )
            print(
                exc,
            )

            if history:
                current_url = history.pop()
                path.pop()
                continue

            return

        if args.trace_js and current_url not in api_checked_urls:
            api_checked_urls.add(
                current_url,
            )
            print()
            print(
                "JS/API tracing enabled. Analyzing JavaScript bundles...",
            )
            candidates = discover_dynamic_content_sources(
                current_url,
                js_bundle_sources=js_bundle_sources,
            )
            api_links = links_from_candidate_endpoints(
                candidates,
                source_page=current_url,
            )

            if api_links:
                page_links = merge_discovered_links(
                    page_links,
                    api_links,
                )

            if prompt_for_api_tracking(
                candidates,
            ):
                return

        include_global_regions = len(
            path,
        ) == 1
        links = links_for_display(
            page_links.links,
            include_global_regions=include_global_regions,
            max_links=args.max_links,
        )
        print_path(
            path,
        )
        print_links(
            links,
        )
        print()
        print("Enter number or full URL, b = back, l = list tracked, r = remove tracked, q = quit")

        value = input(
            "Selection: ",
        ).strip()

        if value.lower() == "q":
            return

        if value.lower() == "b":
            if history:
                current_url = history.pop()
                path.pop()
            else:
                print(
                    "No previous page.",
                )
            continue

        if value.lower() == "l":
            print_tracked_roots()
            continue

        if value.lower() == "r":
            remove_tracked_root()
            continue

        selected_url = choose_link(
            value,
            links,
        )

        if not selected_url:
            continue

        option = selected_url_menu(
            selected_url,
        )

        if option == "e":
            history.append(
                current_url,
            )
            current_url = selected_url
            path.append(
                selected_url,
            )
            continue

        if option == "t":
            track_root(
                selected_url,
                trace_js=args.trace_js,
                js_bundle_sources=js_bundle_sources
                if args.trace_js and js_bundle_sources
                else None,
            )
            next_step = input(
                "Continue exploring? [y/N]: ",
            ).strip().lower()

            if next_step != "y":
                return

            continue

        if option == "o":
            print(
                selected_url,
            )


if __name__ == "__main__":
    main()
