from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Iterable

from mysignal.discovery.categorizer import categorize_url
from mysignal.discovery.filters import is_content_url, normalize_url


UrlCrawler = Callable[..., Iterable[str]]


@dataclass(frozen=True)
class HubDiscovery:
    website: str
    discovered_urls: list[str]
    content_urls: list[str]
    grouped_hubs: dict[str, list[str]]

    @property
    def total_content(self) -> int:
        return len(self.content_urls)


def discover_content_hubs(
    website: str,
    crawl: UrlCrawler,
) -> HubDiscovery:
    discovered_urls = sorted(
        crawl(
            website,
        )
    )

    normalized_urls = {
        normalize_url(
            url,
        )
        for url in discovered_urls
    }

    content_urls = sorted(
        url
        for url in normalized_urls
        if is_content_url(
            url,
        )
    )

    grouped_hubs = defaultdict(list)

    for url in content_urls:
        grouped_hubs[
            categorize_url(
                url,
            )
        ].append(
            url,
        )

    return HubDiscovery(
        website=website,
        discovered_urls=discovered_urls,
        content_urls=content_urls,
        grouped_hubs=dict(
            sorted(
                grouped_hubs.items(),
            )
        ),
    )
