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

from mysignal.monitoring.inventory_store import (
    load_tracked_recursive_targets,
)
from mysignal.workflows.api_monitor import (
    baseline_seen_urls_from_apis,
)
from mysignal.workflows.parent_monitor import (
    baseline_seen_urls_from_parents,
)


def main() -> None:
    tracked_targets = load_tracked_recursive_targets()
    tracked_parents = [
        target
        for target in tracked_targets
        if target.strategy == "parent"
    ]
    tracked_apis = [
        target.url
        for target in tracked_targets
        if target.strategy == "api"
    ]

    if not tracked_parents and not tracked_apis:
        print(
            "No tracked parent/API URLs found. Run scripts/explore_setup.py first.",
        )
        return

    added = {}

    if tracked_parents:
        added.update(
            baseline_seen_urls_from_parents(
                tracked_parents,
            )
        )

    if tracked_apis:
        added.update(
            baseline_seen_urls_from_apis(
                tracked_apis,
            )
        )

    print()
    print("BASELINE COMPLETE")
    print("=" * 60)
    print(
        f"TRACKED PARENTS: {len(tracked_parents)}",
    )
    print(
        f"TRACKED APIS: {len(tracked_apis)}",
    )
    print(
        f"URLS ADDED TO SEEN STORAGE: {len(added)}",
    )


if __name__ == "__main__":
    main()
