import asyncio
import os
from unittest.mock import patch
import unittest

from mysignal.discovery.page_links import DiscoveredLink, extract_page_links_async


class HangingCrawler:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def arun(self, **kwargs):
        await asyncio.Future()


class PageLinksTimeoutTests(unittest.TestCase):
    def test_crawl_timeout_falls_back_to_requests_link_extraction(self):
        fallback = {
            "https://example.com/story": DiscoveredLink(
                url="https://example.com/story",
                source_page="https://example.com",
                region="main",
            )
        }
        with (
            patch("mysignal.discovery.page_links.AsyncWebCrawler", return_value=HangingCrawler()),
            patch("mysignal.discovery.page_links.extract_links_with_requests", return_value=fallback),
            patch.dict(os.environ, {"CRAWL4AI_TIMEOUT_SECONDS": "1"}),
        ):
            result = asyncio.run(extract_page_links_async("https://example.com"))

        self.assertEqual([item.url for item in result.links], ["https://example.com/story"])


if __name__ == "__main__":
    unittest.main()
