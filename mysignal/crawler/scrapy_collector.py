import asyncio

from collections import deque

from bs4 import BeautifulSoup

from mysignal.crawler.scrapy_fetcher import fetch_url
from mysignal.discovery.page_links import (
    company_domain,
    normalize_discovered_href,
)

from mysignal.discovery.filters import (
    is_hub_url,
)

MAX_PAGES = 200
MAX_DEPTH = 2
MARKDOWN_URL_PATTERN = r"https://[^\s\)\]\"<]+"


def clean_discovered_url(
    url: str,
):
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


async def discover_urls(
    website_url: str,
    *,
    max_pages: int = MAX_PAGES,
    max_depth: int = MAX_DEPTH,
):
    import re

    discovered = set()

    candidate_urls = set()

    queue = deque(
        [(website_url.rstrip("/"), 0)]
    )

    root_company = company_domain(
        website_url,
    )

    while (
        queue
        and len(discovered) < max_pages
    ):

        current_url, depth = (
            queue.popleft()
        )

        if current_url in discovered:
            continue

        print(
            f"CRAWLING [D{depth}]: "
            f"{current_url}"
        )

        discovered.add(
            current_url
        )

        try:
            result = await asyncio.to_thread(
                fetch_url,
                current_url,
            )
        except Exception as e:

            print(
                f"ERROR: {current_url}"
            )

            print(e)

            continue

        #
        # Stop expanding deeper
        #
        if depth >= max_depth:
            continue

        soup = BeautifulSoup(
            result.text or "",
            "html.parser",
        )
        internal_links = [
            anchor.get(
                "href",
                "",
            )
            for anchor in soup.find_all(
                "a",
                href=True,
            )
        ]

        #
        # URLs discovered in visible text
        #
        markdown_urls = re.findall(
            MARKDOWN_URL_PATTERN,
            soup.get_text(
                " ",
                strip=True,
            ),
        )

        internal_links.extend(
            markdown_urls,
        )

        for href in internal_links:
            normalized = normalize_discovered_href(
                href,
                result.url,
            )

            if not normalized:
                continue

            #
            # Only same company
            #
            if company_domain(
                normalized,
            ) != root_company:
                continue

            if (
                normalized
                in discovered
            ):
                continue

            candidate_urls.add(
                normalized
            )

            #
            # Homepage expands only into hubs.
            #
            if depth == 0:

                if is_hub_url(
                    normalized
                ):

                    queue.append(
                        (
                            normalized,
                            depth + 1,
                        )
                    )

                continue

            #
            # Hubs recurse into hubs.
            #
            if is_hub_url(
                normalized
            ):

                queue.append(
                    (
                        normalized,
                        depth + 1,
                    )
                )

    return sorted(
        candidate_urls
    )
                


def crawl_site(
    website_url: str,
    *,
    max_pages: int = MAX_PAGES,
    max_depth: int = MAX_DEPTH,
):
    return asyncio.run(
        discover_urls(
            website_url,
            max_pages=max_pages,
            max_depth=max_depth,
        )
    )

