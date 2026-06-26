import json
from dataclasses import dataclass
from pathlib import Path


DATA_DIR = Path(
    "mysignal/data"
)

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

INVENTORY_FILE = (
    DATA_DIR
    / "inventory.json"
)

TRACKED_HUBS_FILE = (
    DATA_DIR
    / "tracked_hubs.json"
)

TRACKED_RECURSIVE_ROOTS_FILE = (
    DATA_DIR
    / "tracked_recursive_roots.json"
)

GLOBAL_URLS_FILE = (
    DATA_DIR
    / "global_urls.json"
)



SEEN_URL_RECORDS_FILE = (
    DATA_DIR
    / "seen_url_records.json"
)


@dataclass(frozen=True)
class TrackedRecursiveRoot:
    url: str
    recipients: list[str]
    strategy: str = "parent"
    trace_js: bool = False
    js_bundle_sources: list[str] | None = None


def _split_recipients(
    recipients,
) -> list[str]:
    if recipients is None:
        return []

    if isinstance(
        recipients,
        str,
    ):
        values = recipients.split(
            ",",
        )
    else:
        values = recipients

    return [
        str(
            recipient,
        ).strip()
        for recipient in values
        if str(
            recipient,
        ).strip()
    ]


def _target_from_entry(
    entry,
) -> TrackedRecursiveRoot | None:
    js_bundle_sources = None
    trace_js = False

    if isinstance(
        entry,
        str,
    ):
        url = entry.strip()
        recipients = []
        strategy = "parent"
    elif isinstance(
        entry,
        dict,
    ):
        url = str(
            entry.get(
                "url",
            )
            or entry.get(
                "root",
            )
            or entry.get(
                "parent_url",
            )
            or ""
        ).strip()
        recipients = _split_recipients(
            entry.get(
                "recipients",
            )
            or entry.get(
                "emails",
            )
            or entry.get(
                "email_recipients",
            )
        )
        strategy = str(
            entry.get(
                "strategy",
                "parent",
            )
        ).strip().lower()
        trace_js = bool(
            entry.get(
                "trace_js",
                False,
            )
        )
        js_bundle_sources = entry.get(
            "js_bundle_sources",
        )
    else:
        return None

    if not url:
        return None

    return TrackedRecursiveRoot(
        url=url,
        recipients=recipients,
        strategy=strategy or "parent",
        trace_js=trace_js,
        js_bundle_sources=(
            [
                str(
                    source,
                ).strip()
                for source in js_bundle_sources
                if str(
                    source,
                ).strip()
            ]
            if isinstance(
                js_bundle_sources,
                list,
            )
            else None
        ),
    )


def _load_tracked_recursive_data():
    if not TRACKED_RECURSIVE_ROOTS_FILE.exists():
        return []

    with open(
        TRACKED_RECURSIVE_ROOTS_FILE,
        "r",
        encoding="utf-8",
    ) as f:

        return json.load(
            f
        )


def load_tracked_recursive_targets() -> list[TrackedRecursiveRoot]:
    data = _load_tracked_recursive_data()

    if isinstance(
        data,
        dict,
    ):
        if "targets" in data:
            entries = data[
                "targets"
            ]
        else:
            entries = [
                {
                    "url": url,
                    "recipients": recipients,
                }
                for url, recipients in data.items()
            ]
    else:
        entries = data

    targets = []
    seen_urls = set()

    for entry in entries:
        target = _target_from_entry(
            entry,
        )

        if target is None:
            continue

        if target.url in seen_urls:
            continue

        targets.append(
            target,
        )
        seen_urls.add(
            target.url,
        )

    return targets


def save_tracked_recursive_targets(
    targets: list[TrackedRecursiveRoot],
):
    serialized_targets = []

    for target in targets:
        serialized_target = {
            "url": target.url,
            "strategy": target.strategy,
            "recipients": target.recipients,
            "trace_js": target.trace_js,
        }

        if target.js_bundle_sources:
            serialized_target[
                "js_bundle_sources"
            ] = target.js_bundle_sources

        serialized_targets.append(
            serialized_target,
        )

    with open(
        TRACKED_RECURSIVE_ROOTS_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            serialized_targets,
            f,
            indent=2,
        )

def load_inventory():

    if not INVENTORY_FILE.exists():
        return {}

    with open(
        INVENTORY_FILE,
        "r",
        encoding="utf-8",
    ) as f:

        return json.load(
            f
        )
def save_inventory(
    inventory,
):
    with open(
        INVENTORY_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            inventory,
            f,
            indent=2,
        )
def load_tracked_hubs():

    if not TRACKED_HUBS_FILE.exists():
        return []

    with open(
        TRACKED_HUBS_FILE,
        "r",
        encoding="utf-8",
    ) as f:

        return json.load(
            f
        )
def save_tracked_hubs(
    hubs,
):
    with open(
        TRACKED_HUBS_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            hubs,
            f,
            indent=2,
        )


def load_tracked_recursive_roots():
    return [
        target.url
        for target in load_tracked_recursive_targets()
        if target.strategy == "parent"
    ]


def save_tracked_recursive_roots(
    roots,
):
    targets = [
        root
        if isinstance(
            root,
            TrackedRecursiveRoot,
        )
        else TrackedRecursiveRoot(
            url=str(
                root,
            ),
            recipients=[],
            strategy="parent",
        )
        for root in roots
    ]

    save_tracked_recursive_targets(
        targets,
    )
def load_global_urls():

    if not GLOBAL_URLS_FILE.exists():
        return {}

    with open(
        GLOBAL_URLS_FILE,
        "r",
        encoding="utf-8",
    ) as f:

        return json.load(
            f
        )


def save_global_urls(
    global_urls,
):
    with open(
        GLOBAL_URLS_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            global_urls,
            f,
            indent=2,
        )

    
def load_seen_url_records():

    if not SEEN_URL_RECORDS_FILE.exists():
        return {}

    with open(
        SEEN_URL_RECORDS_FILE,
        "r",
        encoding="utf-8",
    ) as f:

        return json.load(
            f
        )


def save_seen_url_records(
    records,
):
    with open(
        SEEN_URL_RECORDS_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            records,
            f,
            indent=2,
        )
