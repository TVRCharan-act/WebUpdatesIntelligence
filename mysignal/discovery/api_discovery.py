from dataclasses import dataclass
import json
import re
from urllib.parse import urljoin, urlparse

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
    r"/news|/stories|/press|application/json",
    re.IGNORECASE,
)
MAX_ENDPOINT_VALIDATIONS = 50
QUOTED_STRING_PATTERN = re.compile(
    r"""["']([^"'\\]*(?:\\.[^"'\\]*)*)["']""",
)
PATH_HINT_PATTERN = re.compile(
    r"(/api/|/graphql|/news|/stories|/press|graphql|news|stories|press|"
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
GRAPHQL_OPERATION_PATTERN = re.compile(
    r"\bquery\s+[A-Za-z0-9_]+|\bmutation\s+[A-Za-z0-9_]+",
)
SCRIPT_PATH_PATTERN = re.compile(
    r"\.js(?:\?|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CandidateEndpoint:
    endpoint_url: str
    discovered_urls: list[str]
    score: int
    detection_method: str
    content_type: str


def same_origin_url(
    url: str,
    page_url: str,
) -> bool:
    return urlparse(
        url,
    ).netloc.lower() == urlparse(
        page_url,
    ).netloc.lower()


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


def fetch_text(
    url: str,
    *,
    accept: str = "*/*",
    timeout: int = 15,
) -> tuple[str, str]:
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
    )


def same_origin_script_urls(
    html: str,
    page_url: str,
    *,
    script_sources: list[str] | None = None,
) -> list[str]:
    soup = BeautifulSoup(
        html or "",
        "html.parser",
    )
    script_urls = []
    seen = set()

    for script in soup.find_all(
        "script",
        src=True,
    ):
        src = script.get(
            "src",
            "",
        ).strip()

        if not src:
            continue

        script_url = urljoin(
            f"{page_url}/",
            src,
        )

        if not same_origin_url(
            script_url,
            page_url,
        ):
            continue

        if script_url in seen:
            continue

        script_urls.append(
            script_url,
        )
        seen.add(
            script_url,
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

            if not SCRIPT_PATH_PATTERN.search(
                src,
            ):
                continue

            script_url = urljoin(
                f"{page_url}/",
                src,
            )

            if not same_origin_url(
                script_url,
                page_url,
            ):
                continue

            if script_url in seen:
                continue

            script_urls.append(
                script_url,
            )
        seen.add(
            script_url,
        )

    for src in script_sources or []:
        src = src.strip()

        if not src:
            continue

        script_url = urljoin(
            f"{page_url}/",
            src,
        )

        if not same_origin_url(
            script_url,
            page_url,
        ):
            continue

        if script_url in seen:
            continue

        script_urls.append(
            script_url,
        )
        seen.add(
            script_url,
        )

    return script_urls


def candidate_endpoint_strings(
    javascript: str,
) -> list[tuple[str, str]]:
    candidates = []

    for pattern, method in (
        (
            FETCH_ENDPOINT_PATTERN,
            "fetch-call",
        ),
        (
            XHR_ENDPOINT_PATTERN,
            "xhr-open",
        ),
    ):
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
                "graphql-hint",
            )
        )

    return candidates


def normalize_endpoint_candidate(
    candidate: str,
    *,
    page_url: str,
    script_url: str,
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
        f"{page_url}/",
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


def validate_json_endpoint(
    endpoint_url: str,
    *,
    page_url: str,
    detection_method: str,
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

    return CandidateEndpoint(
        endpoint_url=endpoint_url,
        discovered_urls=discovered_urls,
        score=len(
            discovered_urls,
        ),
        detection_method=detection_method,
        content_type=content_type,
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
        html, _content_type = fetch_text(
            normalized_page_url,
            accept="text/html",
        )
    except Exception:
        return []

    script_urls = same_origin_script_urls(
        html,
        normalized_page_url,
        script_sources=script_sources,
    )
    endpoint_methods: dict[str, set[str]] = {}

    for script_url in script_urls:
        try:
            javascript, _content_type = fetch_text(
                script_url,
            )
        except Exception:
            continue

        if not API_HINT_PATTERN.search(
            javascript,
        ):
            continue

        for candidate, method in candidate_endpoint_strings(
            javascript,
        ):
            for endpoint_url in normalize_endpoint_candidate(
                candidate,
                page_url=normalized_page_url,
                script_url=script_url,
            ):
                if not same_origin_url(
                    endpoint_url,
                    normalized_page_url,
                ):
                    continue

                endpoint_methods.setdefault(
                    endpoint_url,
                    set(),
                ).add(
                    method,
                )

    validated = []

    prioritized_endpoint_methods = sorted(
        endpoint_methods.items(),
        key=lambda item: endpoint_priority(
            item[0],
        ),
        reverse=True,
    )[
        :MAX_ENDPOINT_VALIDATIONS
    ]

    for endpoint_url, methods in prioritized_endpoint_methods:
        candidate = validate_json_endpoint(
            endpoint_url,
            page_url=normalized_page_url,
            detection_method=",".join(
                sorted(
                    methods,
                )
            ),
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
