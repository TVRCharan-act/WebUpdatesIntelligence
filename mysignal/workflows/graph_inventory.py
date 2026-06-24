from typing import Iterable, Mapping

from mysignal.discovery.site_graph import (
    SiteGraph,
    leaf_descendants,
    normalize_graph_url,
)


INVENTORY_NODE_TYPES = {
    "article",
    "unknown",
}


def build_inventory_for_graph_roots(
    graph: SiteGraph,
    selected_roots: Iterable[str],
) -> dict[str, list[str]]:
    inventory: dict[str, list[str]] = {}

    for root in selected_roots:
        normalized_root = normalize_graph_url(
            root,
        )
        leaf_urls = leaf_descendants(
            graph,
            normalized_root,
        )
        inventory[
            normalized_root
        ] = sorted(
            url
            for url in leaf_urls
            if graph.nodes.get(
                url,
            )
            and graph.nodes[
                url
            ].type
            in INVENTORY_NODE_TYPES
        )

    return inventory


def find_new_graph_inventory_urls(
    previous_inventory: Mapping[str, Iterable[str]],
    current_inventory: Mapping[str, Iterable[str]],
    selected_roots: Iterable[str],
) -> dict[str, list[str]]:
    changes: dict[str, list[str]] = {}

    for root in selected_roots:
        normalized_root = normalize_graph_url(
            root,
        )
        previous_urls = set(
            previous_inventory.get(
                normalized_root,
                [],
            )
        )
        current_urls = set(
            current_inventory.get(
                normalized_root,
                [],
            )
        )
        new_urls = sorted(
            current_urls
            - previous_urls
        )

        if new_urls:
            changes[
                normalized_root
            ] = new_urls

    return changes
