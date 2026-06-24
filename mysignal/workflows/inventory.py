from dataclasses import dataclass
from typing import Callable, Iterable, Mapping

from mysignal.monitoring.inventory_monitor import (
    build_url_frequency,
    remove_common_urls,
)


InventoryFetcher = Callable[..., Iterable[str]]


@dataclass(frozen=True)
class HubFetchError:
    hub: str
    error: Exception


@dataclass(frozen=True)
class InventoryBuild:
    raw_inventory: dict[str, list[str]]
    inventory: dict[str, list[str]]
    frequency: dict[str, int]
    errors: list[HubFetchError]


def build_inventory_for_hubs(
    hubs: Iterable[str],
    fetch_inventory: InventoryFetcher,
    *,
    common_url_threshold: int = 2,
) -> InventoryBuild:
    selected_hubs = list(
        hubs,
    )
    known_hubs = set(
        selected_hubs,
    )
    raw_inventory: dict[str, list[str]] = {}
    errors: list[HubFetchError] = []

    for hub in selected_hubs:
        try:
            raw_inventory[
                hub
            ] = sorted(
                fetch_inventory(
                    hub,
                    known_hubs,
                )
            )
        except Exception as exc:
            errors.append(
                HubFetchError(
                    hub=hub,
                    error=exc,
                )
            )

    frequency = build_url_frequency(
        raw_inventory,
    )

    inventory = {
        hub: sorted(
            remove_common_urls(
                urls,
                frequency,
                threshold=common_url_threshold,
            )
        )
        for hub, urls in raw_inventory.items()
    }

    return InventoryBuild(
        raw_inventory=raw_inventory,
        inventory=inventory,
        frequency=frequency,
        errors=errors,
    )


def find_new_inventory_urls(
    previous_inventory: Mapping[str, Iterable[str]],
    current_inventory: Mapping[str, Iterable[str]],
    hubs: Iterable[str],
) -> dict[str, list[str]]:
    changes: dict[str, list[str]] = {}

    for hub in hubs:
        previous_urls = set(
            previous_inventory.get(
                hub,
                [],
            )
        )
        current_urls = set(
            current_inventory.get(
                hub,
                [],
            )
        )
        new_urls = sorted(
            current_urls
            - previous_urls
        )

        if new_urls:
            changes[
                hub
            ] = new_urls

    return changes
