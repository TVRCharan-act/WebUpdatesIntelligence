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