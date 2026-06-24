from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import re
from urllib.parse import urlparse

from mysignal.discovery.filters import NEGATIVE_TERMS


ASSET_EXTENSIONS = {
    ".css",
    ".js",
    ".json",
    ".xml",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".pdf",
    ".zip",
    ".csv",
    ".xlsx",
    ".docx",
}

LISTING_TERMS = {
    "news",
    "blog",
    "blogs",
    "research",
    "press",
    "newsroom",
    "media",
    "stories",
    "story",
    "publication",
    "publications",
    "announcement",
    "announcements",
    "update",
    "updates",
    "insight",
    "insights",
    "article",
    "articles",
    "page",
    "category",
    "tag",
    "archive",
}

DATE_PATH_PATTERN = re.compile(r"/(?:19|20)\d{2}(?:/|-)\d{1,2}(?:/|-)\d{1,2}")


@dataclass(frozen=True)
class GraphNode:
    url: str
    type: str
    depth: int
    title: str | None = None


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    source_type: str


@dataclass(frozen=True)
class SiteGraph:
    root_url: str
    nodes: dict[str, GraphNode]
    edges: list[GraphEdge]


def normalize_graph_url(url: str) -> str:
    parsed = urlparse(
        url.strip(),
    )

    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")

    if not path:
        path = ""

    return f"{scheme}://{netloc}{path}"


def _path_segments(url: str) -> list[str]:
    return [
        segment
        for segment in urlparse(url).path.lower().split("/")
        if segment
    ]


def _has_asset_extension(path: str) -> bool:
    return any(
        path.endswith(
            extension,
        )
        for extension in ASSET_EXTENSIONS
    )


def _has_long_slug(segments: list[str]) -> bool:
    if not segments:
        return False

    last_segment = segments[-1]
    slug_parts = [
        part
        for part in re.split(r"[-_]", last_segment)
        if part
    ]

    return len(last_segment) >= 24 or len(slug_parts) >= 5


def classify_url(
    url: str,
) -> str:
    parsed = urlparse(
        url,
    )
    path = parsed.path.lower()
    segments = _path_segments(
        url,
    )

    if not path or path == "/":
        return "root"

    if _has_asset_extension(
        path,
    ):
        return "asset"

    if any(
        term in segments
        for term in NEGATIVE_TERMS
    ):
        return "ignored"

    if DATE_PATH_PATTERN.search(
        path,
    ) or _has_long_slug(
        segments,
    ):
        return "article"

    if any(
        term in segments
        for term in LISTING_TERMS
    ):
        if len(
            segments,
        ) <= 3:
            return "hub"

        return "listing"

    return "unknown"


def is_expandable_node(
    node_type: str,
) -> bool:
    return node_type in {
        "root",
        "hub",
        "listing",
        "unknown",
    }


def _children_by_source(
    graph: SiteGraph,
) -> dict[str, set[str]]:
    children: dict[str, set[str]] = defaultdict(set)

    for edge in graph.edges:
        children[
            edge.source
        ].add(
            edge.target,
        )

    return children


def descendants(
    graph: SiteGraph,
    selected_url: str,
) -> set[str]:
    selected_url = normalize_graph_url(
        selected_url,
    )
    children = _children_by_source(
        graph,
    )
    found: set[str] = set()
    queue = deque(
        children.get(
            selected_url,
            set(),
        )
    )

    while queue:
        url = queue.popleft()

        if url in found:
            continue

        found.add(
            url,
        )

        queue.extend(
            children.get(
                url,
                set(),
            )
        )

    return found


def leaf_descendants(
    graph: SiteGraph,
    selected_url: str,
) -> set[str]:
    children = _children_by_source(
        graph,
    )

    return {
        url
        for url in descendants(
            graph,
            selected_url,
        )
        if not children.get(
            url,
        )
        or graph.nodes.get(
            url,
            GraphNode(
                url=url,
                type="unknown",
                depth=0,
            ),
        ).type
        == "article"
    }
