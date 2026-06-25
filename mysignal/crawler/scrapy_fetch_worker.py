import base64
import json
import sys

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.core.downloader import Slot as DownloaderSlot


_original_slot_init = DownloaderSlot.__init__


# Scrapy 2.16 on this Python environment leaves simple slotted defaults unset.
def _patched_slot_init(
    self,
    *args,
    **kwargs,
):
    _original_slot_init(
        self,
        *args,
        **kwargs,
    )

    if not hasattr(
        self,
        "lastseen",
    ):
        self.lastseen = 0

    if not hasattr(
        self,
        "latercall",
    ):
        self.latercall = None


DownloaderSlot.__init__ = _patched_slot_init


class FetchSpider(scrapy.Spider):
    name = "mysignal_fetch"
    custom_settings = {
        "DOWNLOAD_TIMEOUT": 30,
        "LOG_ENABLED": False,
        "ROBOTSTXT_OBEY": False,
        "USER_AGENT": "mysignal-scrapy-fetcher/1.0",
    }

    def __init__(
        self,
        *,
        urls: list[str],
        results: list[dict],
        errors: list[str],
        **kwargs,
    ):
        super().__init__(
            **kwargs,
        )
        self.urls = urls
        self.results = results
        self.errors = errors

    async def start(
        self,
    ):
        for url in self.urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                errback=self.handle_error,
                dont_filter=True,
            )

    def parse(
        self,
        response,
    ):
        self.results.append(
            {
                "url": response.url,
                "status": response.status,
                "text": response.text,
                "body": base64.b64encode(
                    response.body,
                ).decode(
                    "ascii",
                ),
            }
        )

    def handle_error(
        self,
        failure,
    ):
        self.errors.append(
            failure.getTraceback()
        )


def main() -> None:
    payload = json.loads(
        sys.stdin.read()
        or "{}",
    )
    urls = payload.get(
        "urls",
        [],
    )
    results: list[dict] = []
    errors: list[str] = []

    process = CrawlerProcess(
        settings={
            "DOWNLOAD_TIMEOUT": 30,
            "LOG_ENABLED": False,
            "ROBOTSTXT_OBEY": False,
            "USER_AGENT": "mysignal-scrapy-fetcher/1.0",
        }
    )
    process.crawl(
        FetchSpider,
        urls=urls,
        results=results,
        errors=errors,
    )
    process.start()

    print(
        json.dumps(
            {
                "results": results,
                "errors": errors,
            }
        )
    )


if __name__ == "__main__":
    main()
