from collections.abc import Callable
from dataclasses import dataclass, field
import json
import re
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup
import requests

from mysignal.discovery.page_links import (
    company_domain,
    normalize_discovered_href,
    normalize_page_url,
)
from mysignal.filters.content_filter import is_content_candidate


API_HINT_PATTERN = re.compile(
    r"fetch\s*\(|axios\s*\(|XMLHttpRequest|graphql|/api/|/graphql|"
    r"/news|/stories|/press|application/json|ApolloClient|urql|Relay|"
    r"persistedQuery|sha256Hash",
    re.IGNORECASE,
)
MAX_ENDPOINT_VALIDATIONS = 50
MAX_SOURCE_MAP_BYTES = 2_000_000
QUOTED_STRING_PATTERN = re.compile(
    r"""["']([^"'\\]*(?:\\.[^"'\\]*)*)["']""",
)
PATH_HINT_PATTERN = re.compile(
    r"(/api/|/graphql|/news|/stories|/press|/blog|/posts|/articles|"
    r"graphql|news|stories|press|blog|posts|articles|content|"
    r"\.json(?:\?|$))",
    re.IGNORECASE,
)
FETCH_ENDPOINT_PATTERN = re.compile(
    r"(?:fetch|axios(?:\.(?:get|post|request))?)\s*\(\s*[\"']([^\"']+)",
    re.IGNORECASE,
)
XHR_ENDPOINT_PATTERN = re.compile(
    r"\.open\s*\(\s*[\"'][A-Z]+[\"']\s*,\s*[\"']([^\"']+)",
    re.IGNORECASE,
)
ENDPOINT_CAPTURE_PATTERNS = (
    (
        FETCH_ENDPOINT_PATTERN,
        "fetch-call",
    ),
    (
        XHR_ENDPOINT_PATTERN,
        "xhr-open",
    ),
)
GRAPHQL_OPERATION_PATTERN = re.compile(
    r"\bquery\s+[A-Za-z0-9_]+|\bmutation\s+[A-Za-z0-9_]+|"
    r"\bfragment\s+[A-Za-z0-9_]+|persistedQuery|sha256Hash",
    re.IGNORECASE,
)
SCRIPT_EXTENSIONS = (
    ".js",
    ".mjs",
    ".cjs",
)
SCRIPT_LIKE_REL_VALUES = {
    "modulepreload",
    "preload",
    "prefetch",
}
SOURCE_MAPPING_URL_PATTERN = re.compile(
    r"sourceMappingURL=([^\s*]+)",
    re.IGNORECASE,
)
WINDOW_STATE_PATTERN = re.compile(
    r"(?:window\.)?(__INITIAL_STATE__|__APOLLO_STATE__|__NUXT__)\s*=",
    re.IGNORECASE,
)
ARTICLE_METADATA_KEYS = {
    "article",
    "articles",
    "author",
    "date",
    "headline",
    "id",
    "published",
    "published_at",
    "publishedat",
    "pubdate",
    "slug",
    "title",
    "updated",
    "updated_at",
    "updatedat",
}
CONTENT_ENDPOINT_TOKENS = (
    "article",
    "articles",
    "blog",
    "content",
    "news",
    "post",
    "posts",
    "press",
    "story",
    "stories",
)
LOW_VALUE_ENDPOINT_TOKENS = (
    "account",
    "admin",
    "asset",
    "auth",
    "cart",
    "config",
    "login",
    "logout",
    "menu",
    "nav",
    "navigation",
    "password",
    "preview",
    "search",
    "session",
    "settings",
    "static",
    "user",
)
COMMON_API_PROBE_PATHS = (
    "/api/posts",
    "/api/news",
    "/api/articles",
    "/api/blog",
    "/api/content",
)


@dataclass(frozen=True)
class FrameworkSignature:
    name: str
    html_markers: tuple[str, ...] = ()
    javascript_markers: tuple[str, ...] = ()
    generator_markers: tuple[str, ...] = ()
    probe_paths: tuple[tuple[str, str], ...] = ()


FRAMEWORK_SIGNATURES = (
    FrameworkSignature(
        name="next.js",
        html_markers=("__next_data__", "/_next/"),
        javascript_markers=("__next_data__", "/_next/"),
    ),
    FrameworkSignature(
        name="nuxt",
        html_markers=("__nuxt__", "/_nuxt/"),
        javascript_markers=("__nuxt__", "/_nuxt/"),
    ),
    FrameworkSignature(
        name="gatsby",
        html_markers=("gatsby", "/page-data/"),
        javascript_markers=("gatsby", "/page-data/"),
        generator_markers=("gatsby",),
    ),
    FrameworkSignature(
        name="astro",
        html_markers=("astro-island", "/_astro/"),
        javascript_markers=("astro", "/_astro/"),
    ),
    FrameworkSignature(
        name="remix",
        html_markers=("__remixcontext", "/build/_assets/"),
        javascript_markers=("remix", "__remixcontext"),
    ),
    FrameworkSignature(
        name="wordpress",
        html_markers=("/wp-content/", "/wp-json/"),
        javascript_markers=("wp-json", "wp-content"),
        generator_markers=("wordpress",),
        probe_paths=(
            ("/wp-json/wp/v2/posts", "wordpress-rest-probe"),
            ("/wp-json/wp/v2/pages", "wordpress-rest-probe"),
        ),
    ),
    FrameworkSignature(
        name="ghost",
        html_markers=("ghost/api", "ghost.org"),
        javascript_markers=("ghost/api", "@tryghost/content-api"),
        generator_markers=("ghost",),
        probe_paths=(("/ghost/api/content/posts/", "ghost-content-probe"),),
    ),
    FrameworkSignature(
        name="contentful",
        html_markers=("cdn.contentful.com", "contentful"),
        javascript_markers=("contentful",),
    ),
    FrameworkSignature(
        name="strapi",
        html_markers=("strapi", "/api/articles"),
        javascript_markers=("strapi",),
    ),
    FrameworkSignature(
        name="sanity",
        html_markers=("cdn.sanity.io", "sanity"),
        javascript_markers=("sanity",),
    ),
)
FRAMEWORK_PRIORITY = tuple(
    signature.name
    for signature in FRAMEWORK_SIGNATURES
)


@dataclass(frozen=True)
class CandidateEndpoint:
    endpoint_url: str
    discovered_urls: list[str]
    score: int
    detection_method: str
    content_type: str
    framework: str | None = None
    validation_result: str = "accepted"
    source_javascript_bundle: str | None = None
    source_map: str | None = None
    embedded_json_source: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass
class EndpointDiscoveryMetadata:
    detection_methods: set[str] = field(
        default_factory=set,
    )
    source_javascript_bundles: set[str] = field(
        default_factory=set,
    )
    source_maps: set[str] = field(
        default_factory=set,
    )
    embedded_json_sources: set[str] = field(
        default_factory=set,
    )
    frameworks: set[str] = field(
        default_factory=set,
    )


def same_origin_url(
    url: str,
    page_url: str,
) -> bool:
    return urlparse(
        url,
    ).netloc.lower() == urlparse(
        page_url,
    ).netloc.lower()


def allowed_script_url(
    url: str,
    page_url: str,
) -> bool:
    return same_origin_url(
        url,
        page_url,
    ) or company_domain(
        url,
    ) == company_domain(
        page_url,
    )


def normalize_api_url(
    url: str,
) -> str:
    parsed = urlparse(
        url.strip(),
    )
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip(
        "/",
    )
    normalized = f"{scheme}://{netloc}{path}"

    if parsed.query:
        normalized = f"{normalized}?{parsed.query}"

    return normalized


def normalize_endpoint_href(
    href: str,
    source_url: str,
) -> str | None:
    href = href.strip().split(
        "#",
        1,
    )[0]

    if not href:
        return None

    parsed = urlparse(
        href,
    )

    if parsed.scheme and parsed.scheme not in {
        "http",
        "https",
    }:
        return None

    absolute_url = urljoin(
        source_url,
        href,
    )

    if not urlparse(
        absolute_url,
    ).netloc:
        return None

    return normalize_api_url(
        absolute_url,
    )


def append_script_url(
    script_urls: list[str],
    seen: set[str],
    *,
    raw_url: str,
    page_url: str,
    base_url: str,
) -> None:
    raw_url = raw_url.strip()

    if not raw_url:
        return

    if raw_url.startswith(
        (
            "data:",
            "blob:",
            "mailto:",
            "tel:",
            "#",
        )
    ):
        return

    parsed_raw_url = urlparse(
        raw_url,
    )
    if not parsed_raw_url.path.lower().endswith(
        SCRIPT_EXTENSIONS,
    ):
        return

    script_url = urldefrag(
        urljoin(
            base_url,
            raw_url,
        )
    )[0]

    if not allowed_script_url(
        script_url,
        page_url,
    ):
        return

    if script_url in seen:
        return

    script_urls.append(
        script_url,
    )
    seen.add(
        script_url,
    )


def fetch_text(
    url: str,
    *,
    accept: str = "*/*",
    timeout: int = 15,
) -> tuple[str, str]:
    text, content_type, _final_url = fetch_text_with_url(
        url,
        accept=accept,
        timeout=timeout,
    )

    return (
        text,
        content_type,
    )


def fetch_text_with_url(
    url: str,
    *,
    accept: str = "*/*",
    timeout: int = 15,
) -> tuple[str, str, str]:
    response = requests.get(
        url,
        timeout=timeout,
        headers={
            "Accept": accept,
            "User-Agent": (
                "Mozilla/5.0 (compatible; MySignalMonitor/1.0)"
            ),
        },
    )
    response.raise_for_status()

    return (
        response.text,
        response.headers.get(
            "content-type",
            "",
        ),
        response.url,
    )


def primary_framework(
    frameworks: set[str],
) -> str | None:
    for framework in FRAMEWORK_PRIORITY:
        if framework in frameworks:
            return framework

    return sorted(
        frameworks,
    )[0] if frameworks else None


def register_endpoint_candidate(
    endpoint_metadata: dict[str, EndpointDiscoveryMetadata],
    endpoint_url: str,
    *,
    detection_method: str,
    framework: str | None = None,
    source_javascript_bundle: str | None = None,
    source_map: str | None = None,
    embedded_json_source: str | None = None,
) -> None:
    metadata = endpoint_metadata.setdefault(
        endpoint_url,
        EndpointDiscoveryMetadata(),
    )
    metadata.detection_methods.add(
        detection_method,
    )

    if framework:
        metadata.frameworks.add(
            framework,
        )

    if source_javascript_bundle:
        metadata.source_javascript_bundles.add(
            source_javascript_bundle,
        )

    if source_map:
        metadata.source_maps.add(
            source_map,
        )

    if embedded_json_source:
        metadata.embedded_json_sources.add(
            embedded_json_source,
        )


def script_text(
    script,
) -> str:
    return script.string or script.get_text(
        "",
        strip=False,
    )


def decode_json_candidate(
    value: str,
) -> Any | None:
    value = value.strip()

    if not value:
        return None

    try:
        return json.loads(
            value,
        )
    except json.JSONDecodeError:
        return None


def balanced_json_text(
    text: str,
    start_index: int,
) -> str | None:
    while start_index < len(
        text,
    ) and text[
        start_index
    ].isspace():
        start_index += 1

    if start_index >= len(
        text,
    ) or text[
        start_index
    ] not in {
        "{",
        "[",
    }:
        return None

    opening = text[
        start_index
    ]
    closing = "}" if opening == "{" else "]"
    depth = 0
    in_string = False
    escaped = False

    for index in range(
        start_index,
        len(
            text,
        ),
    ):
        char = text[
            index
        ]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1

            if depth == 0:
                return text[
                    start_index : index + 1
                ]

    return None


def extract_embedded_json_state(
    html: str,
) -> list[tuple[str, Any]]:
    soup = BeautifulSoup(
        html or "",
        "html.parser",
    )
    states: list[tuple[str, Any]] = []

    for script in soup.find_all(
        "script",
    ):
        source_name = None
        script_id = str(
            script.get(
                "id",
                "",
            )
        ).strip()
        script_type = str(
            script.get(
                "type",
                "",
            )
        ).strip().lower()
        text = script_text(
            script,
        )

        if script_id == "__NEXT_DATA__":
            source_name = "__NEXT_DATA__"
        elif script_type == "application/ld+json":
            source_name = "application/ld+json"
        elif script_type == "application/json":
            source_name = (
                script_id
                or "application/json"
            )

        if source_name:
            data = decode_json_candidate(
                text,
            )

            if data is not None:
                states.append(
                    (
                        source_name,
                        data,
                    )
                )

        if not text:
            continue

        for match in WINDOW_STATE_PATTERN.finditer(
            text,
        ):
            json_text = balanced_json_text(
                text,
                match.end(),
            )

            if not json_text:
                continue

            data = decode_json_candidate(
                json_text,
            )

            if data is not None:
                states.append(
                    (
                        match.group(
                            1,
                        ),
                        data,
                    )
                )

    return states


def detect_frameworks_from_markers(
    text: str,
    marker_field: str,
) -> set[str]:
    lowered = (
        text or ""
    ).lower()
    frameworks: set[str] = set()

    for signature in FRAMEWORK_SIGNATURES:
        markers = getattr(
            signature,
            marker_field,
        )
        if any(
            marker in lowered
            for marker in markers
        ):
            frameworks.add(
                signature.name,
            )

    return frameworks


def detect_frameworks_from_generator_meta(
    soup: BeautifulSoup,
) -> set[str]:
    frameworks: set[str] = set()

    for meta in soup.find_all(
        "meta",
    ):
        if str(
            meta.get(
                "name",
                "",
            )
        ).lower() != "generator":
            continue

        content = str(
            meta.get(
                "content",
                "",
            )
        ).lower()

        for signature in FRAMEWORK_SIGNATURES:
            if any(
                marker in content
                for marker in signature.generator_markers
            ):
                frameworks.add(
                    signature.name,
                )

    return frameworks


def detect_frameworks_from_html(
    html: str,
) -> set[str]:
    soup = BeautifulSoup(
        html or "",
        "html.parser",
    )
    frameworks = detect_frameworks_from_markers(
        html,
        "html_markers",
    )
    frameworks.update(
        detect_frameworks_from_generator_meta(
            soup,
        )
    )

    return frameworks


def detect_frameworks_from_javascript(
    javascript: str,
) -> set[str]:
    return detect_frameworks_from_markers(
        javascript,
        "javascript_markers",
    )


def next_data_probe_urls(
    page_url: str,
    embedded_states: list[tuple[str, Any]],
) -> list[str]:
    build_ids = []

    for source, data in embedded_states:
        if source != "__NEXT_DATA__" or not isinstance(
            data,
            dict,
        ):
            continue

        build_id = data.get(
            "buildId",
        )

        if build_id:
            build_ids.append(
                str(
                    build_id,
                )
            )

    if not build_ids:
        return []

    parsed = urlparse(
        page_url,
    )
    route_path = parsed.path.strip(
        "/",
    ) or "index"

    if route_path.endswith(
        ".json",
    ):
        route_path = route_path[
            :-5
        ]

    return [
        normalize_api_url(
            urljoin(
                page_url,
                f"/_next/data/{build_id}/{route_path}.json",
            )
        )
        for build_id in sorted(
            set(
                build_ids,
            )
        )
    ]


DYNAMIC_FRAMEWORK_PROBES: dict[
    str,
    tuple[str, Callable[[str, list[tuple[str, Any]]], list[str]]],
] = {
    "next.js": (
        "next-data-probe",
        next_data_probe_urls,
    ),
}


def framework_probe_urls(
    page_url: str,
    frameworks: set[str],
    embedded_states: list[tuple[str, Any]],
) -> list[tuple[str, str]]:
    probes: list[tuple[str, str]] = []

    for path in COMMON_API_PROBE_PATHS:
        probes.append(
            (
                normalize_api_url(
                    urljoin(
                        page_url,
                        path,
                    )
                ),
                "common-api-probe",
            )
        )

    for framework in sorted(
        frameworks,
    ):
        dynamic_probe = DYNAMIC_FRAMEWORK_PROBES.get(
            framework,
        )

        if not dynamic_probe:
            continue

        method, probe_builder = dynamic_probe
        for probe in probe_builder(
            page_url,
            embedded_states,
        ):
            probes.append(
                (
                    probe,
                    method,
                )
            )

    for signature in FRAMEWORK_SIGNATURES:
        if signature.name not in frameworks:
            continue

        for path, method in signature.probe_paths:
            probes.append(
                (
                    normalize_api_url(
                        urljoin(
                            page_url,
                            path,
                        )
                    ),
                    method,
                )
            )

    return probes


def same_origin_script_urls(
    html: str,
    page_url: str,
    *,
    base_url: str | None = None,
    script_sources: list[str] | None = None,
) -> list[str]:
    soup = BeautifulSoup(
        html or "",
        "html.parser",
    )
    script_urls = []
    seen = set()
    resolution_base_url = base_url or page_url

    for script in soup.find_all(
        "script",
        src=True,
    ):
        append_script_url(
            script_urls,
            seen,
            raw_url=script.get(
                "src",
                "",
            ),
            page_url=page_url,
            base_url=resolution_base_url,
        )

    for link in soup.find_all(
        "link",
        href=True,
    ):
        rel_values = {
            str(
                rel,
            ).lower()
            for rel in link.get(
                "rel",
                [],
            )
        }
        as_value = str(
            link.get(
                "as",
                "",
            )
        ).lower()

        if not (
            rel_values & SCRIPT_LIKE_REL_VALUES
            or as_value in {
                "script",
                "worker",
            }
        ):
            continue

        append_script_url(
            script_urls,
            seen,
            raw_url=link.get(
                "href",
                "",
            ),
            page_url=page_url,
            base_url=resolution_base_url,
        )

    for script in soup.find_all(
        "script",
    ):
        if script.get(
            "src",
        ):
            continue

        script_text = script.string or script.get_text(
            "",
            strip=False,
        )

        if not script_text:
            continue

        for match in QUOTED_STRING_PATTERN.finditer(
            script_text,
        ):
            src = bytes(
                match.group(
                    1,
                ),
                "utf-8",
            ).decode(
                "unicode_escape",
                errors="ignore",
            )

            append_script_url(
                script_urls,
                seen,
                raw_url=src,
                page_url=page_url,
                base_url=resolution_base_url,
            )

    for src in script_sources or []:
        append_script_url(
            script_urls,
            seen,
            raw_url=src,
            page_url=page_url,
            base_url=resolution_base_url,
        )

    return script_urls


def discover_js_bundle_sources(
    page_url: str,
    *,
    script_sources: list[str] | None = None,
) -> list[str]:
    normalized_page_url = normalize_page_url(
        page_url,
    )
    html, _content_type, final_url = fetch_text_with_url(
        normalized_page_url,
        accept="text/html",
    )

    return same_origin_script_urls(
        html,
        normalized_page_url,
        base_url=final_url,
        script_sources=script_sources,
    )


def candidate_endpoint_strings(
    javascript: str,
) -> list[tuple[str, str]]:
    candidates = []

    for pattern, method in ENDPOINT_CAPTURE_PATTERNS:
        for match in pattern.finditer(
            javascript,
        ):
            candidates.append(
                (
                    match.group(
                        1,
                    ),
                    method,
                )
            )

    if API_HINT_PATTERN.search(
        javascript,
    ):
        for match in QUOTED_STRING_PATTERN.finditer(
            javascript,
        ):
            value = bytes(
                match.group(
                    1,
                ),
                "utf-8",
            ).decode(
                "unicode_escape",
                errors="ignore",
            )

            if PATH_HINT_PATTERN.search(
                value,
            ):
                candidates.append(
                    (
                        value,
                        "script-string",
                    )
                )

    if GRAPHQL_OPERATION_PATTERN.search(
        javascript,
    ):
        candidates.append(
            (
                "/graphql",
                "graphql-client-hint",
            )
        )

    return candidates


def discover_source_map_urls(
    javascript: str,
    script_url: str,
) -> list[str]:
    urls = []

    for match in SOURCE_MAPPING_URL_PATTERN.finditer(
        javascript or "",
    ):
        value = match.group(
            1,
        ).strip()

        if value.startswith(
            "data:",
        ):
            continue

        normalized = normalize_endpoint_href(
            value,
            script_url,
        )

        if normalized:
            urls.append(
                normalized,
            )

    parsed = urlparse(
        script_url,
    )

    if parsed.path.endswith(
        ".js",
    ):
        default_map_url = normalize_endpoint_href(
            f"{parsed.path}.map",
            f"{parsed.scheme}://{parsed.netloc}",
        )

        if default_map_url:
            urls.append(
                default_map_url,
            )

    return sorted(
        set(
            urls,
        )
    )


def fetch_source_map(
    map_url: str,
) -> dict[str, Any] | None:
    try:
        text, content_type = fetch_text(
            map_url,
            accept="application/json,*/*",
            timeout=8,
        )
    except Exception:
        return None

    if len(
        text,
    ) > MAX_SOURCE_MAP_BYTES:
        return None

    if "json" not in content_type.lower() and not map_url.lower().endswith(
        ".map",
    ):
        return None

    try:
        data = json.loads(
            text,
        )
    except json.JSONDecodeError:
        return None

    if not isinstance(
        data,
        dict,
    ):
        return None

    return data


def source_map_sources(
    source_map: dict[str, Any],
) -> list[str]:
    values = source_map.get(
        "sourcesContent",
    )

    if not isinstance(
        values,
        list,
    ):
        return []

    return [
        value
        for value in values
        if isinstance(
            value,
            str,
        )
    ]


def graphql_operation_names(
    javascript: str,
) -> list[str]:
    names = []

    for match in re.finditer(
        r"\b(?:query|mutation|subscription)\s+([A-Za-z0-9_]+)",
        javascript or "",
    ):
        names.append(
            match.group(
                1,
            )
        )

    return sorted(
        set(
            names,
        )
    )


def persisted_query_hashes(
    javascript: str,
) -> list[str]:
    hashes = []

    for match in re.finditer(
        r"sha256Hash[\"']?\s*[:=]\s*[\"']([A-Fa-f0-9]{32,64})[\"']",
        javascript or "",
    ):
        hashes.append(
            match.group(
                1,
            )
        )

    return sorted(
        set(
            hashes,
        )
    )


def normalize_endpoint_candidate(
    candidate: str,
    *,
    page_url: str,
    script_url: str,
    page_base_url: str | None = None,
) -> list[str]:
    candidate = candidate.strip()

    if not candidate:
        return []

    if not (
        candidate.startswith(
            (
                "http://",
                "https://",
                "/",
                "./",
                "../",
            )
        )
        or ".json" in candidate.lower()
        or "?" in candidate
    ):
        return []

    if any(
        token in candidate
        for token in (
            "{",
            "}",
            "${",
            " ",
            "\n",
            "\t",
        )
    ):
        return []

    if candidate.startswith(
        (
            "data:",
            "blob:",
            "mailto:",
            "tel:",
            "#",
        )
    ):
        return []

    urls = []

    for base_url in (
        page_base_url or page_url,
        script_url,
    ):
        normalized = normalize_endpoint_href(
            candidate,
            base_url,
        )

        if normalized:
            urls.append(
                normalized,
            )

    return sorted(
        set(
            urls,
        )
    )


def endpoint_priority(
    endpoint_url: str,
) -> tuple[int, str]:
    lowered = endpoint_url.lower()
    score = 0

    if ".json" in lowered:
        score += 5

    for token in (
        "/api/",
        "/graphql",
        "/news",
        "/stories",
        "/press",
    ):
        if token in lowered:
            score += 2

    return (
        score,
        endpoint_url,
    )


def is_json_url_like(
    value: str,
) -> bool:
    stripped = value.strip()

    if not stripped or any(
        char.isspace()
        for char in stripped
    ):
        return False

    return stripped.startswith(
        (
            "http://",
            "https://",
            "/",
            "./",
            "../",
        )
    ) or "/" in stripped


def extract_json_urls(
    value,
    *,
    page_url: str,
    root_company: str,
) -> list[str]:
    urls = []

    if isinstance(
        value,
        dict,
    ):
        iterable = value.values()
    elif isinstance(
        value,
        list,
    ):
        iterable = value
    elif isinstance(
        value,
        str,
    ):
        if not is_json_url_like(
            value,
        ):
            return urls

        normalized_url = normalize_discovered_href(
            value,
            page_url,
        )

        if (
            normalized_url
            and company_domain(
                normalized_url,
            )
            == root_company
            and is_content_candidate(
                normalized_url,
            )
        ):
            urls.append(
                normalize_page_url(
                    normalized_url,
                )
            )

        return urls
    else:
        return urls

    for child in iterable:
        urls.extend(
            extract_json_urls(
                child,
                page_url=page_url,
                root_company=root_company,
            )
        )

    return urls


def json_stats(
    value: Any,
) -> dict[str, int]:
    stats = {
        "objects": 0,
        "lists": 0,
        "strings": 0,
        "article_metadata_keys": 0,
        "date_like_values": 0,
    }

    def visit(
        item: Any,
    ) -> None:
        if isinstance(
            item,
            dict,
        ):
            stats[
                "objects"
            ] += 1

            for key, child in item.items():
                normalized_key = str(
                    key,
                ).lower().replace(
                    "-",
                    "_",
                )

                if normalized_key in ARTICLE_METADATA_KEYS:
                    stats[
                        "article_metadata_keys"
                    ] += 1

                visit(
                    child,
                )
        elif isinstance(
            item,
            list,
        ):
            stats[
                "lists"
            ] += 1

            for child in item:
                visit(
                    child,
                )
        elif isinstance(
            item,
            str,
        ):
            stats[
                "strings"
            ] += 1

            if re.search(
                r"\b20\d{2}-\d{2}-\d{2}\b|\b20\d{2}/\d{2}/\d{2}\b",
                item,
            ):
                stats[
                    "date_like_values"
                ] += 1

    visit(
        value,
    )

    return stats


def response_size_score(
    response_size: int,
) -> int:
    if response_size <= 2:
        return -20

    if response_size < 200:
        return -10

    if response_size < 2_000:
        return 5

    if response_size < 200_000:
        return 10

    return 4


def endpoint_name_score(
    endpoint_url: str,
) -> int:
    lowered = endpoint_url.lower()
    score = 0

    for token in CONTENT_ENDPOINT_TOKENS:
        if token in lowered:
            score += 8

    if ".json" in lowered:
        score += 5

    if "/api/" in lowered:
        score += 4

    if "/graphql" in lowered:
        score += 3

    for token in LOW_VALUE_ENDPOINT_TOKENS:
        if token in lowered:
            score -= 12

    return score


def weighted_endpoint_score(
    *,
    endpoint_url: str,
    discovered_urls: list[str],
    page_url: str,
    data: Any,
    response_text: str,
    detection_method: str,
) -> tuple[int, dict[str, Any]]:
    stats = json_stats(
        data,
    )
    root_company = company_domain(
        page_url,
    )
    same_domain_urls = [
        url
        for url in discovered_urls
        if company_domain(
            url,
        )
        == root_company
    ]
    score = 0
    score += min(
        len(
            discovered_urls,
        )
        * 12,
        48,
    )
    score += min(
        len(
            same_domain_urls,
        )
        * 4,
        16,
    )
    score += min(
        stats[
            "article_metadata_keys"
        ]
        * 3,
        24,
    )
    score += endpoint_name_score(
        endpoint_url,
    )
    score += min(
        stats[
            "objects"
        ]
        + stats[
            "lists"
        ],
        12,
    )
    score += response_size_score(
        len(
            response_text,
        )
    )
    score += min(
        stats[
            "date_like_values"
        ]
        * 2,
        10,
    )

    if "probe" in detection_method:
        score -= 2

    if not discovered_urls:
        score -= 25

    if stats[
        "objects"
    ] == 0 and stats[
        "lists"
    ] == 0:
        score -= 25

    confidence = max(
        0,
        min(
            100,
            score,
        ),
    )

    return (
        confidence,
        {
            "discovered_url_count": len(
                discovered_urls,
            ),
            "same_domain_url_count": len(
                same_domain_urls,
            ),
            "article_metadata_key_count": stats[
                "article_metadata_keys"
            ],
            "date_like_value_count": stats[
                "date_like_values"
            ],
            "json_object_count": stats[
                "objects"
            ],
            "json_list_count": stats[
                "lists"
            ],
            "response_size_bytes": len(
                response_text,
            ),
        },
    )


def metadata_dict(
    *,
    validation_result: str,
    framework: str | None,
    methods: list[str],
    source_javascript_bundle: str | None,
    source_map: str | None,
    embedded_json_source: str | None,
    score_details: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "detection_method": ",".join(
            methods,
        ),
        "framework": framework,
        "confidence_score": score_details,
        "validation_result": validation_result,
        "source_javascript_bundle": source_javascript_bundle,
        "source_map": source_map,
        "embedded_json_source": embedded_json_source,
    }

    if extra:
        data.update(
            extra,
        )

    return data


def validate_json_endpoint(
    endpoint_url: str,
    *,
    page_url: str,
    detection_method: str,
    framework: str | None = None,
    source_javascript_bundle: str | None = None,
    source_map: str | None = None,
    embedded_json_source: str | None = None,
) -> CandidateEndpoint | None:
    try:
        text, content_type = fetch_text(
            endpoint_url,
            accept="application/json",
            timeout=8,
        )
    except Exception:
        return None

    if "json" not in content_type.lower():
        return None

    try:
        data = json.loads(
            text,
        )
    except json.JSONDecodeError:
        return None

    discovered_urls = sorted(
        set(
            extract_json_urls(
                data,
                page_url=page_url,
                root_company=company_domain(
                    page_url,
                ),
            )
        )
    )

    score, score_details = weighted_endpoint_score(
        endpoint_url=endpoint_url,
        discovered_urls=discovered_urls,
        page_url=page_url,
        data=data,
        response_text=text,
        detection_method=detection_method,
    )
    validation_result = "accepted" if score else "low-confidence"
    methods = sorted(
        {
            method
            for method in detection_method.split(
                ",",
            )
            if method
        }
    )

    return CandidateEndpoint(
        endpoint_url=endpoint_url,
        discovered_urls=discovered_urls,
        score=score,
        detection_method=detection_method,
        content_type=content_type,
        framework=framework,
        validation_result=validation_result,
        source_javascript_bundle=source_javascript_bundle,
        source_map=source_map,
        embedded_json_source=embedded_json_source,
        metadata=metadata_dict(
            validation_result=validation_result,
            framework=framework,
            methods=methods,
            source_javascript_bundle=source_javascript_bundle,
            source_map=source_map,
            embedded_json_source=embedded_json_source,
            score_details=score_details,
        ),
    )


def embedded_json_candidate(
    page_url: str,
    embedded_states: list[tuple[str, Any]],
    *,
    frameworks: set[str],
) -> CandidateEndpoint | None:
    urls = []
    sources = []
    combined_data = []

    for source, data in embedded_states:
        extracted_urls = extract_json_urls(
            data,
            page_url=page_url,
            root_company=company_domain(
                page_url,
            ),
        )

        if extracted_urls:
            urls.extend(
                extracted_urls,
            )
            sources.append(
                source,
            )
            combined_data.append(
                data,
            )

    discovered_urls = sorted(
        set(
            urls,
        )
    )

    if not discovered_urls:
        return None

    response_text = json.dumps(
        combined_data,
        separators=(
            ",",
            ":",
        ),
    )
    score, score_details = weighted_endpoint_score(
        endpoint_url=page_url,
        discovered_urls=discovered_urls,
        page_url=page_url,
        data=combined_data,
        response_text=response_text,
        detection_method="embedded-json-state",
    )
    source_name = ",".join(
        sorted(
            set(
                sources,
            )
        )
    )
    framework = primary_framework(
        frameworks,
    )

    return CandidateEndpoint(
        endpoint_url=page_url,
        discovered_urls=discovered_urls,
        score=score,
        detection_method="embedded-json-state",
        content_type="text/html",
        framework=framework,
        validation_result="accepted",
        embedded_json_source=source_name,
        metadata=metadata_dict(
            validation_result="accepted",
            framework=framework,
            methods=[
                "embedded-json-state",
            ],
            source_javascript_bundle=None,
            source_map=None,
            embedded_json_source=source_name,
            score_details=score_details,
        ),
    )


def validate_graphql_endpoint(
    endpoint_url: str,
    *,
    page_url: str,
    detection_method: str,
    framework: str | None = None,
    source_javascript_bundle: str | None = None,
    source_map: str | None = None,
    operation_names: list[str] | None = None,
    persisted_hashes: list[str] | None = None,
) -> CandidateEndpoint | None:
    introspection_query = (
        "query IntrospectionQuery { __schema { queryType { name } "
        "mutationType { name } types { name kind } } }"
    )

    try:
        response = requests.post(
            endpoint_url,
            timeout=8,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (compatible; MySignalMonitor/1.0)"
                ),
            },
            json={
                "query": introspection_query,
            },
        )
    except Exception:
        return None

    content_type = response.headers.get(
        "content-type",
        "",
    )

    if "json" not in content_type.lower():
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    if not isinstance(
        data,
        dict,
    ):
        return None

    schema = data.get(
        "data",
        {},
    ).get(
        "__schema",
    )
    introspection_enabled = isinstance(
        schema,
        dict,
    )
    schema_type_names = []

    if introspection_enabled:
        schema_type_names = [
            str(
                item.get(
                    "name",
                    "",
                )
            )
            for item in schema.get(
                "types",
                [],
            )
            if isinstance(
                item,
                dict,
            )
        ]

    content_operation_names = [
        name
        for name in operation_names or []
        if any(
            token in name.lower()
            for token in CONTENT_ENDPOINT_TOKENS
        )
    ]
    content_schema_types = [
        name
        for name in schema_type_names
        if any(
            token in name.lower()
            for token in CONTENT_ENDPOINT_TOKENS
        )
    ]

    if (
        not introspection_enabled
        and not content_operation_names
        and not persisted_hashes
    ):
        return None

    score = 0

    if introspection_enabled:
        score += 20

    score += min(
        len(
            content_operation_names,
        )
        * 8,
        24,
    )
    score += min(
        len(
            content_schema_types,
        )
        * 3,
        24,
    )

    if persisted_hashes:
        score += 8

    score += endpoint_name_score(
        endpoint_url,
    )
    score = max(
        0,
        min(
            100,
            score,
        ),
    )
    validation_result = (
        "accepted-introspection"
        if introspection_enabled
        else "accepted-graphql-json"
    )
    methods = sorted(
        {
            method
            for method in detection_method.split(
                ",",
            )
            if method
        }
    )

    return CandidateEndpoint(
        endpoint_url=endpoint_url,
        discovered_urls=[],
        score=score,
        detection_method=detection_method,
        content_type=content_type,
        framework=framework,
        validation_result=validation_result,
        source_javascript_bundle=source_javascript_bundle,
        source_map=source_map,
        metadata=metadata_dict(
            validation_result=validation_result,
            framework=framework,
            methods=methods,
            source_javascript_bundle=source_javascript_bundle,
            source_map=source_map,
            embedded_json_source=None,
            score_details={
                "introspection_enabled": introspection_enabled,
                "content_operation_count": len(
                    content_operation_names,
                ),
                "content_schema_type_count": len(
                    content_schema_types,
                ),
                "persisted_query_hash_count": len(
                    persisted_hashes or [],
                ),
            },
            extra={
                "graphql_operation_names": operation_names or [],
                "graphql_content_operations": content_operation_names,
                "persisted_query_hashes": persisted_hashes or [],
            },
        ),
    )


def discover_api_endpoints(
    page_url,
    *,
    script_sources: list[str] | None = None,
) -> list[CandidateEndpoint]:
    normalized_page_url = normalize_page_url(
        page_url,
    )

    try:
        html, _content_type, final_url = fetch_text_with_url(
            normalized_page_url,
            accept="text/html",
        )
    except Exception:
        return []

    embedded_states = extract_embedded_json_state(
        html,
    )
    frameworks = detect_frameworks_from_html(
        html,
    )
    script_urls = same_origin_script_urls(
        html,
        normalized_page_url,
        base_url=final_url,
        script_sources=script_sources,
    )
    endpoint_metadata: dict[str, EndpointDiscoveryMetadata] = {}
    graphql_operation_names_by_endpoint: dict[str, set[str]] = {}
    persisted_hashes_by_endpoint: dict[str, set[str]] = {}

    for endpoint_url, method in framework_probe_urls(
        normalized_page_url,
        frameworks,
        embedded_states,
    ):
        if same_origin_url(
            endpoint_url,
            normalized_page_url,
        ):
            register_endpoint_candidate(
                endpoint_metadata,
                endpoint_url,
                detection_method=method,
                framework=primary_framework(
                    frameworks,
                ),
            )

    for script_url in script_urls:
        try:
            javascript, _content_type = fetch_text(
                script_url,
            )
        except Exception:
            continue

        script_frameworks = detect_frameworks_from_javascript(
            javascript,
        )
        frameworks.update(
            script_frameworks,
        )
        script_graphql_operations = graphql_operation_names(
            javascript,
        )
        script_persisted_hashes = persisted_query_hashes(
            javascript,
        )

        if API_HINT_PATTERN.search(
            javascript,
        ):
            for candidate, method in candidate_endpoint_strings(
                javascript,
            ):
                for endpoint_url in normalize_endpoint_candidate(
                    candidate,
                    page_url=normalized_page_url,
                    script_url=script_url,
                    page_base_url=final_url,
                ):
                    if not same_origin_url(
                        endpoint_url,
                        normalized_page_url,
                    ):
                        continue

                    register_endpoint_candidate(
                        endpoint_metadata,
                        endpoint_url,
                        detection_method=method,
                        framework=primary_framework(
                            script_frameworks or frameworks,
                        ),
                        source_javascript_bundle=script_url,
                    )

                    if "graphql" in endpoint_url.lower():
                        graphql_operation_names_by_endpoint.setdefault(
                            endpoint_url,
                            set(),
                        ).update(
                            script_graphql_operations,
                        )
                        persisted_hashes_by_endpoint.setdefault(
                            endpoint_url,
                            set(),
                        ).update(
                            script_persisted_hashes,
                        )

        for source_map_url in discover_source_map_urls(
            javascript,
            script_url,
        ):
            if not same_origin_url(
                source_map_url,
                normalized_page_url,
            ):
                continue

            source_map = fetch_source_map(
                source_map_url,
            )

            if not source_map:
                continue

            for source_text in source_map_sources(
                source_map,
            ):
                frameworks.update(
                    detect_frameworks_from_javascript(
                        source_text,
                    )
                )
                map_graphql_operations = graphql_operation_names(
                    source_text,
                )
                map_persisted_hashes = persisted_query_hashes(
                    source_text,
                )

                if not API_HINT_PATTERN.search(
                    source_text,
                ):
                    continue

                for candidate, method in candidate_endpoint_strings(
                    source_text,
                ):
                    for endpoint_url in normalize_endpoint_candidate(
                        candidate,
                        page_url=normalized_page_url,
                        script_url=script_url,
                        page_base_url=final_url,
                    ):
                        if not same_origin_url(
                            endpoint_url,
                            normalized_page_url,
                        ):
                            continue

                        register_endpoint_candidate(
                            endpoint_metadata,
                            endpoint_url,
                            detection_method=f"source-map:{method}",
                            framework=primary_framework(
                                frameworks,
                            ),
                            source_javascript_bundle=script_url,
                            source_map=source_map_url,
                        )

                        if "graphql" in endpoint_url.lower():
                            graphql_operation_names_by_endpoint.setdefault(
                                endpoint_url,
                                set(),
                            ).update(
                                map_graphql_operations,
                            )
                            persisted_hashes_by_endpoint.setdefault(
                                endpoint_url,
                                set(),
                            ).update(
                                map_persisted_hashes,
                            )

    for endpoint_url, method in framework_probe_urls(
        normalized_page_url,
        frameworks,
        embedded_states,
    ):
        if same_origin_url(
            endpoint_url,
            normalized_page_url,
        ):
            register_endpoint_candidate(
                endpoint_metadata,
                endpoint_url,
                detection_method=method,
                framework=primary_framework(
                    frameworks,
                ),
            )

    validated = []
    embedded_candidate = embedded_json_candidate(
        normalized_page_url,
        embedded_states,
        frameworks=frameworks,
    )

    if embedded_candidate:
        validated.append(
            embedded_candidate,
        )

    prioritized_endpoint_metadata = sorted(
        endpoint_metadata.items(),
        key=lambda item: endpoint_priority(
            item[0],
        ),
        reverse=True,
    )[
        :MAX_ENDPOINT_VALIDATIONS
    ]

    for endpoint_url, discovery_metadata in prioritized_endpoint_metadata:
        methods = sorted(
            discovery_metadata.detection_methods,
        )
        detection_method = ",".join(
            methods,
        )
        framework = primary_framework(
            discovery_metadata.frameworks or frameworks,
        )
        source_javascript_bundle = (
            sorted(
                discovery_metadata.source_javascript_bundles,
            )[0]
            if discovery_metadata.source_javascript_bundles
            else None
        )
        source_map = (
            sorted(
                discovery_metadata.source_maps,
            )[0]
            if discovery_metadata.source_maps
            else None
        )
        embedded_json_source = (
            sorted(
                discovery_metadata.embedded_json_sources,
            )[0]
            if discovery_metadata.embedded_json_sources
            else None
        )

        if "graphql" in endpoint_url.lower():
            candidate = validate_graphql_endpoint(
                endpoint_url,
                page_url=normalized_page_url,
                detection_method=detection_method,
                framework=framework,
                source_javascript_bundle=source_javascript_bundle,
                source_map=source_map,
                operation_names=sorted(
                    graphql_operation_names_by_endpoint.get(
                        endpoint_url,
                        set(),
                    )
                ),
                persisted_hashes=sorted(
                    persisted_hashes_by_endpoint.get(
                        endpoint_url,
                        set(),
                    )
                ),
            )
        else:
            candidate = validate_json_endpoint(
                endpoint_url,
                page_url=normalized_page_url,
                detection_method=detection_method,
                framework=framework,
                source_javascript_bundle=source_javascript_bundle,
                source_map=source_map,
                embedded_json_source=embedded_json_source,
            )

        if candidate and candidate.score:
            validated.append(
                candidate,
            )

    return sorted(
        validated,
        key=lambda endpoint: (
            endpoint.score,
            endpoint.endpoint_url,
        ),
        reverse=True,
    )
