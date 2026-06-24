import json
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


def save_tracked_recursive_roots(
    roots,
):
    with open(
        TRACKED_RECURSIVE_ROOTS_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            roots,
            f,
            indent=2,
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