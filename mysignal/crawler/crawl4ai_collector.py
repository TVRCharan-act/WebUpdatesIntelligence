from crawl4ai import AsyncWebCrawler

import asyncio

from collections import deque

from urllib.parse import (
    urlparse,
    urljoin,
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

    root_domain = (
        urlparse(
            website_url
        ).netloc
    )

    root_company = ".".join(
        root_domain.split(".")[-2:]
    )

    async with AsyncWebCrawler() as crawler:

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

                result = await crawler.arun(
                    url=current_url
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

            #
            # Normal internal links
            #
            internal_links = (
                result.links.get(
                    "internal",
                    []
                )
            )

            #
            # URLs discovered in markdown
            #
            markdown_urls = re.findall(
                MARKDOWN_URL_PATTERN,
                result.markdown or "",
            )

            #
            # Convert markdown URLs into
            # same structure as links
            #
            for markdown_url in markdown_urls:

                internal_links.append(
                    {
                        "href":
                        markdown_url
                    }
                )

            for link in internal_links:

                href = link.get(
                    "href"
                )

                if not href:
                    continue

                href = clean_discovered_url(
                    href.split(
                        "#"
                    )[0]
                )

                if not href:
                    continue

                if (
                    href.startswith(
                        "mailto:"
                    )
                    or href.startswith(
                        "tel:"
                    )
                ):
                    continue

                href = urljoin(
                    current_url,
                    href,
                )

                parsed = urlparse(
                    href
                )

                if not parsed.netloc:
                    continue

                candidate_company = ".".join(
                    parsed.netloc.split(".")[-2:]
                )

                #
                # Only same company
                #
                if (
                    candidate_company
                    != root_company
                ):
                    continue

                normalized = (
                    href.rstrip("/")
                )

                if (
                    normalized
                    in discovered
                ):
                    continue

                candidate_urls.add(
                    normalized
                )

                #
                # Homepage expands
                # only into hubs
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
                # Hubs recurse into hubs
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

