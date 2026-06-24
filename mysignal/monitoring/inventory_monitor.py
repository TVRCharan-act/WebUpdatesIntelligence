from crawl4ai import AsyncWebCrawler
import asyncio
import re
from collections import Counter
from mysignal.discovery.filters import (
    normalize_url,
)

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


def build_url_frequency(
    inventories: dict,
):
    frequency = Counter()

    for urls in inventories.values():

        for url in urls:

            frequency[url] += 1

    return dict(
        frequency
    )

def remove_common_urls(
    urls,
    frequency,
    threshold=2,
):
    return {

        url

        for url in urls

        if frequency.get(
            url,
            0
        ) < threshold

    }

def extract_urls_from_markdown(
    markdown: str,
):
    matches = re.findall(
        MARKDOWN_URL_PATTERN,
        markdown,
    )

    return {

        clean_discovered_url(
            url
        )

        for url in matches

    }
    
async def extract_links(
    hub_url,
    known_hubs,
    *,
    preview_chars=0,
):
    urls = set()

    async with AsyncWebCrawler() as crawler:

        result = await crawler.arun(
            url=hub_url
        )
        markdown = result.markdown or ""

        if preview_chars:
            print()
            print("=" * 80)
            print("MARKDOWN PREVIEW")
            print("=" * 80)

            print(
                markdown[:preview_chars]
            )

            print()

        urls = (
            extract_urls_from_markdown(
                markdown
            )
        )
        normalized_urls = set()

        for url in urls:
            normalized_url = normalize_url(
                url,
            )

            if normalized_url in known_hubs:
                continue

            normalized_urls.add(
                normalized_url,
            )

        urls = normalized_urls
    return urls

def fetch_inventory(
    hub_url,
    known_hubs,
    *,
    preview_chars=0,
):
    return asyncio.run(
        extract_links(
            hub_url,
            known_hubs,
            preview_chars=preview_chars,
        )
    )
    
def find_new_urls(
    old_urls,
    current_urls,
):
    return sorted(
        current_urls
        - old_urls
    )
