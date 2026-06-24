from collections import Counter
from dataclasses import dataclass
from typing import Iterable


DEFAULT_GLOBAL_MIN_PARENT_COUNT = 4
DEFAULT_GLOBAL_PARENT_RATIO = 0.20


@dataclass(frozen=True)
class GlobalLinkRules:
    min_parent_count: int = DEFAULT_GLOBAL_MIN_PARENT_COUNT
    parent_ratio: float = DEFAULT_GLOBAL_PARENT_RATIO


def learn_global_urls(
    parent_to_urls: dict[str, Iterable[str]],
    *,
    rules: GlobalLinkRules = GlobalLinkRules(),
) -> set[str]:
    total_parent_pages = len(parent_to_urls)

    if total_parent_pages == 0:
        return set()

    counts = Counter()

    for urls in parent_to_urls.values():
        for url in set(urls):
            counts[url] += 1

    global_urls = set()

    for url, count in counts.items():
        ratio = count / total_parent_pages

        if (
            count >= rules.min_parent_count
            and ratio >= rules.parent_ratio
        ):
            global_urls.add(url)

    return global_urls


def remove_global_urls(
    urls: Iterable[str],
    global_urls: set[str],
) -> list[str]:
    return sorted(
        url
        for url in urls
        if url not in global_urls
    )