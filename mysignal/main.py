import argparse
from functools import partial

from mysignal.crawler.crawl4ai_collector import crawl_site
from mysignal.monitoring.inventory_monitor import fetch_inventory
from mysignal.monitoring.inventory_store import save_inventory, save_tracked_hubs
from mysignal.workflows.discovery import HubDiscovery, discover_content_hubs
from mysignal.workflows.inventory import InventoryBuild, build_inventory_for_hubs


DEFAULT_WEBSITE = "https://example.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover content hubs and build the first inventory.",
    )
    parser.add_argument(
        "website",
        nargs="?",
        default=DEFAULT_WEBSITE,
        help=f"Website to discover. Defaults to {DEFAULT_WEBSITE}.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=200,
        help="Maximum pages to crawl while discovering hubs.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="Maximum crawl depth while discovering hubs.",
    )
    parser.add_argument(
        "--common-url-threshold",
        type=int,
        default=2,
        help="Drop inventory URLs that appear in this many hubs.",
    )
    return parser.parse_args()


def print_discovered_urls(discovery: HubDiscovery) -> None:
    print()
    print(
        f"TOTAL URLS DISCOVERED: {len(discovery.discovered_urls)}",
    )
    print()
    print("=" * 60)
    print("DISCOVERED URLS")
    print("=" * 60)

    for url in discovery.discovered_urls:
        print(url)


def print_content_hubs(discovery: HubDiscovery) -> None:
    print()
    print("=" * 60)
    print("CONTENT HUBS FOUND")
    print("=" * 60)

    for category, urls in discovery.grouped_hubs.items():
        print()
        print(
            f"{category.upper()} ({len(urls)})",
        )
        print("-" * 40)

        for url in urls:
            print(url)

    print()
    print("=" * 60)
    print(
        f"CONTENT URLS: {discovery.total_content}",
    )
    print("=" * 60)


def prompt_for_hubs(discovery: HubDiscovery) -> list[str]:
    numbered_hubs: list[str] = []
    counter = 1

    print()
    print("SELECT HUBS TO TRACK")
    print("=" * 60)

    for category, urls in discovery.grouped_hubs.items():
        print()
        print(
            category.upper(),
        )
        print("-" * 40)

        for url in urls:
            print(
                f"{counter}. {url}",
            )
            numbered_hubs.append(
                url,
            )
            counter += 1

    print()

    selection = input(
        "Enter hub numbers (comma separated): ",
    )

    selected_hubs = []

    for value in selection.split(","):
        value = value.strip()

        if not value:
            continue

        try:
            index = int(
                value,
            ) - 1
        except ValueError:
            print(
                f"Skipping invalid selection: {value}",
            )
            continue

        if 0 <= index < len(numbered_hubs):
            selected_hubs.append(
                numbered_hubs[
                    index
                ]
            )
        else:
            print(
                f"Skipping out-of-range selection: {value}",
            )

    return selected_hubs


def print_inventory_build(build: InventoryBuild) -> None:
    for hub, urls in build.raw_inventory.items():
        print()
        print(
            f"BUILDING INVENTORY: {hub}",
        )
        print(
            f"FOUND {len(urls)} URLS",
        )

    for error in build.errors:
        print()
        print(
            f"FAILED: {error.hub}",
        )
        print(
            error.error,
        )

    print()
    print("=" * 60)
    print("URL FREQUENCY MAP")
    print("=" * 60)

    for url, count in sorted(
        build.frequency.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:20]:
        print(
            f"{count}x -> {url}",
        )


def main() -> None:
    args = parse_args()

    print()
    print(
        f"DISCOVERING: {args.website}",
    )

    crawler = partial(
        crawl_site,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
    )
    discovery = discover_content_hubs(
        args.website,
        crawler,
    )

    print_discovered_urls(
        discovery,
    )
    print_content_hubs(
        discovery,
    )

    selected_hubs = prompt_for_hubs(
        discovery,
    )

    print()
    print(
        f"TRACKING {len(selected_hubs)} HUBS...",
    )

    save_tracked_hubs(
        selected_hubs,
    )

    build = build_inventory_for_hubs(
        selected_hubs,
        fetch_inventory,
        common_url_threshold=args.common_url_threshold,
    )

    print_inventory_build(
        build,
    )

    save_inventory(
        build.inventory,
    )

    print()
    print("=" * 60)
    print("INITIAL INVENTORY CREATED")
    print("=" * 60)
    print(
        f"TRACKED HUBS: {len(selected_hubs)}",
    )
    print(
        f"INVENTORY ENTRIES: {len(build.inventory)}",
    )


if __name__ == "__main__":
    main()
