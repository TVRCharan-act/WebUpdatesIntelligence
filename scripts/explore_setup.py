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

from mysignal.discovery.page_links import (
    GLOBAL_REGIONS,
    DiscoveredLink,
    extract_page_links,
    normalize_page_url,
)
from mysignal.monitoring.inventory_store import (
    load_tracked_recursive_roots,
    save_tracked_recursive_roots,
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
    tracked_roots = load_tracked_recursive_roots()

    print()
    print("TRACKED Parent ROOTS")
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
        print(
            f"{index}. {root}",
        )


def track_root(
    selected_url: str,
) -> None:
    tracked_roots = load_tracked_recursive_roots()

    if selected_url not in tracked_roots:
        tracked_roots.append(
            selected_url,
        )
        save_tracked_recursive_roots(
            tracked_roots,
        )
        print(
            f"Tracking recursively: {selected_url}",
        )
        return

    print(
        f"Already tracking: {selected_url}",
    )


def remove_tracked_root() -> None:
    tracked_roots = load_tracked_recursive_roots()

    if not tracked_roots:
        print(
            "No tracked roots to remove.",
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
            ]
    else:
        remove_url = normalize_page_url(
            value,
        )

    if not remove_url or remove_url not in tracked_roots:
        print(
            "Tracked root not found.",
        )
        return

    tracked_roots.remove(
        remove_url,
    )
    save_tracked_recursive_roots(
        tracked_roots,
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
    current_url = normalize_page_url(
        args.website,
    )
    history: list[str] = []
    path: list[str] = [
        current_url,
    ]

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
