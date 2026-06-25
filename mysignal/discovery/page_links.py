import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse

os.environ.setdefault(
    "CRAWL4_AI_BASE_DIRECTORY",
    str(
        Path(
            "mysignal/data/crawl4ai",
        ).resolve()
    ),
)

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig


MARKDOWN_URL_PATTERN = r"https://[^\s\)\]\"<]+"
GLOBAL_REGIONS = {
    "nav",
    "footer",
    "sidebar",
}
REGION_SORT_ORDER = {
    "nav": 0,
    "sidebar": 1,
    "footer": 2,
    "main": 3,
    "other": 4,
}


@dataclass(frozen=True)
class DiscoveredLink:
    url: str
    source_page: str
    region: str
    label: str | None = None
    source: str = "link"


@dataclass(frozen=True)
class PageLinks:
    page_url: str
    links: list[DiscoveredLink]


def clean_discovered_url(
    url: str,
) -> str:
    return (
        url.split(
            "<",
            1,
        )[0]
        .strip()
        .rstrip(
            "/.,;:'\""
        )
    )


def company_domain(
    url: str,
) -> str:
    netloc = urlparse(
        url,
    ).netloc.lower()
    parts = [
        part
        for part in netloc.split(
            ".",
        )
        if part
    ]

    return ".".join(
        parts[-2:],
    )


def normalize_page_url(
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

    return f"{scheme}://{netloc}{path}"


def normalize_discovered_href(
    href: str,
    source_url: str,
) -> str | None:
    href = href.strip()

    if not href:
        return None

    if href.startswith(
        "mailto:",
    ) or href.startswith(
        "tel:",
    ):
        return None

    href = clean_discovered_url(
        href.split(
            "#",
            1,
        )[0]
    )

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

    return normalize_page_url(
        absolute_url,
    )


def is_same_company_url(
    url: str,
    root_company: str,
) -> bool:
    return company_domain(
        url,
    ) == root_company


def markdown_links(
    markdown: str,
) -> list[str]:
    return [
        clean_discovered_url(
            url,
        )
        for url in re.findall(
            MARKDOWN_URL_PATTERN,
            markdown or "",
        )
    ]


def node_text(
    node,
) -> str | None:
    text = node.get_text(
        " ",
        strip=True,
    )

    if text:
        return text

    for field in (
        "aria-label",
        "title",
    ):
        value = node.get(
            field,
        )

        if value:
            return str(
                value,
            ).strip()

    return None


def node_tokens(
    node,
) -> set[str]:
    values: list[str] = []

    for field in (
        "id",
        "class",
        "role",
    ):
        value = node.get(
            field,
        )

        if isinstance(
            value,
            list,
        ):
            values.extend(
                value,
            )
        elif value:
            values.append(
                str(
                    value,
                )
            )

    return {
        token.lower()
        for value in values
        for token in re.split(
            r"[\s_\-]+",
            value,
        )
        if token
    }


def link_region(
    anchor,
) -> str:
    for node in [
        anchor,
        *anchor.parents,
    ]:
        name = getattr(
            node,
            "name",
            None,
        )

        if not name:
            continue

        tokens = node_tokens(
            node,
        )

        if name == "footer":
            return "footer"

        if name == "aside" or "sidebar" in tokens:
            return "sidebar"

        if name in {
            "nav",
            "header",
        } or "navigation" in tokens or "menu" in tokens:
            return "nav"

        if name in {
            "main",
            "article",
        } or "content" in tokens:
            return "main"

    return "other"


def sort_links(
    links: list[DiscoveredLink],
) -> list[DiscoveredLink]:
    return sorted(
        links,
        key=lambda link: (
            REGION_SORT_ORDER.get(
                link.region,
                REGION_SORT_ORDER[
                    "other"
                ],
            ),
            link.url,
        ),
    )


def extract_html_links(
    html: str,
    page_url: str,
    *,
    same_company_only: bool,
) -> dict[str, DiscoveredLink]:
    soup = BeautifulSoup(
        html or "",
        "html.parser",
    )
    root_company = company_domain(
        page_url,
    )
    links: dict[str, DiscoveredLink] = {}

    for anchor in soup.find_all(
        "a",
        href=True,
    ):
        normalized_url = normalize_discovered_href(
            anchor.get(
                "href",
                "",
            ),
            page_url,
        )

        if not normalized_url:
            continue

        if same_company_only and not is_same_company_url(
            normalized_url,
            root_company,
        ):
            continue

        region = link_region(
            anchor,
        )
        existing = links.get(
            normalized_url,
        )

        if existing and REGION_SORT_ORDER[
            existing.region
        ] <= REGION_SORT_ORDER[
            region
        ]:
            continue

        links[
            normalized_url
        ] = DiscoveredLink(
            url=normalized_url,
            source_page=page_url,
            region=region,
            label=node_text(
                anchor,
            ),
            source="link",
        )

    return links


def extract_markdown_links(
    markdown: str,
    page_url: str,
    existing_urls: set[str],
    *,
    same_company_only: bool,
) -> dict[str, DiscoveredLink]:
    root_company = company_domain(
        page_url,
    )
    links: dict[str, DiscoveredLink] = {}

    for href in markdown_links(
        markdown,
    ):
        normalized_url = normalize_discovered_href(
            href,
            page_url,
        )

        if not normalized_url or normalized_url in existing_urls:
            continue

        if same_company_only and not is_same_company_url(
            normalized_url,
            root_company,
        ):
            continue

        links[
            normalized_url
        ] = DiscoveredLink(
            url=normalized_url,
            source_page=page_url,
            region="main",
            source="markdown",
        )

    return links


async def extract_page_links_async(
    page_url: str,
    *,
    same_company_only: bool = True,
) -> PageLinks:
    normalized_page_url = normalize_page_url(
        page_url,
    )

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=normalized_page_url,
            config=CrawlerRunConfig(
                cache_mode=CacheMode.DISABLED,
            ),
        )

    if getattr(
        result,
        "success",
        True,
    ) is False:
        raise RuntimeError(
            getattr(
                result,
                "error_message",
                "Crawl4AI failed to fetch the page.",
            )
        )

    html = (
        getattr(
            result,
            "html",
            None,
        )
        or getattr(
            result,
            "cleaned_html",
            None,
        )
        or ""
    )
    links = extract_html_links(
        html,
        normalized_page_url,
        same_company_only=same_company_only,
    )

    for link in (result.links or {}).get("internal", []):
        normalized_url = normalize_discovered_href(
            link.get("href", ""),
            normalized_page_url,
        )

        if not normalized_url:
            continue

        if normalized_url in links:
            continue

        if same_company_only and not is_same_company_url(
            normalized_url,
            company_domain(normalized_page_url),
        ):
            continue

        links[normalized_url] = DiscoveredLink(
            url=normalized_url,
            source_page=normalized_page_url,
            region="main",
            label=link.get("text") or link.get("title"),
            source="crawl4ai",
        )

    links.update(
        extract_markdown_links(
            result.markdown or "",
            normalized_page_url,
            set(
                links.keys(),
            ),
            same_company_only=same_company_only,
        )
    )

    return PageLinks(
        page_url=normalized_page_url,
        links=sort_links(
            list(
                links.values(),
            )
        ),
    )


def extract_page_links(
    page_url: str,
    *,
    same_company_only: bool = True,
) -> PageLinks:
    return asyncio.run(
        extract_page_links_async(
            page_url,
            same_company_only=same_company_only,
        )
    )
