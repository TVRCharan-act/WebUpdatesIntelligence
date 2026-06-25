from pathlib import Path
import sys


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

from mysignal.discovery.page_links import normalize_page_url
from mysignal.workflows.feed_monitor import (
    discover_new_urls_from_feeds,
    normalize_feed_url,
)
from mysignal.workflows.new_url_processor import (
    process_new_url_record,
)
from mysignal.workflows.parent_monitor import (
    discover_new_urls_from_parents,
)
from mysignal.monitoring.inventory_store import (
    load_tracked_recursive_targets,
)


def main() -> None:
    tracked_targets = load_tracked_recursive_targets()
    tracked_parents = [
        normalize_page_url(
            target.url,
        )
        for target in tracked_targets
        if target.strategy == "parent"
    ]
    tracked_feeds = [
        normalize_feed_url(
            target.url,
        )
        for target in tracked_targets
        if target.strategy == "feed"
    ]
    recipients_by_source = {
        (
            normalize_feed_url(
                target.url,
            )
            if target.strategy == "feed"
            else normalize_page_url(
                target.url,
            )
        ): target.recipients
        for target in tracked_targets
    }

    if not tracked_parents and not tracked_feeds:
        print(
            "No tracked sources found. Run scripts/explore_setup.py first.",
        )
        return

    parent_new_urls = []
    parent_new_records = {}
    feed_new_urls = []
    feed_new_records = {}

    if tracked_parents:
        parent_new_urls, parent_new_records = discover_new_urls_from_parents(
            tracked_parents,
            store_new_urls=False,
        )

    if tracked_feeds:
        feed_new_urls, feed_new_records = discover_new_urls_from_feeds(
            tracked_feeds,
            store_new_urls=False,
        )

    print()
    print("SOURCE MONITORING COMPLETE")
    print("=" * 60)
    print(
        f"TRACKED PARENTS: {len(tracked_parents)}",
    )
    print(
        f"TRACKED FEEDS: {len(tracked_feeds)}",
    )
    print(
        f"NEW URLS FOUND: {len(parent_new_urls) + len(feed_new_urls)}",
    )

    for url in parent_new_urls:
        record = parent_new_records[
            url
        ]
        parent_url = record[
            "parent_url"
        ]
        recipients = recipients_by_source.get(
            parent_url,
            [],
        )

        process_new_url_record(
            url=url,
            record=record,
            recipients=recipients,
        )

    for url in feed_new_urls:
        record = feed_new_records[
            url
        ]
        feed_url = record[
            "feed_url"
        ]
        recipients = recipients_by_source.get(
            feed_url,
            [],
        )

        process_new_url_record(
            url=url,
            record=record,
            recipients=recipients,
        )


if __name__ == "__main__":
    main()
