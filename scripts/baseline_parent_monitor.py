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
    load_tracked_recursive_roots,
)
from mysignal.workflows.parent_monitor import (
    baseline_seen_urls_from_parents,
)


def main() -> None:
    tracked_parents = load_tracked_recursive_roots()

    if not tracked_parents:
        print(
            "No tracked parent URLs found. Run scripts/explore_setup.py first.",
        )
        return

    added = baseline_seen_urls_from_parents(
        tracked_parents,
    )

    print()
    print("BASELINE COMPLETE")
    print("=" * 60)
    print(
        f"TRACKED PARENTS: {len(tracked_parents)}",
    )
    print(
        f"URLS ADDED TO SEEN STORAGE: {len(added)}",
    )


if __name__ == "__main__":
    main()