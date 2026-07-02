from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import mysignal.discovery.advanced_discovery as advanced
from mysignal.discovery.advanced_discovery import (
    DiscoveryAdapter,
    DiscoveryEndpoint,
    DiscoveryHeavyLock,
    adapter_from_dict,
    adapter_to_dict,
)


class AdvancedDiscoveryAdapterTests(unittest.TestCase):
    def test_adapter_from_dict_keeps_get_endpoints_only(self):
        adapter = adapter_from_dict(
            {
                "domain": "example.com",
                "endpoints": [
                    {"url": "https://example.com/api/articles", "method": "GET"},
                    {"url": "https://example.com/api/admin", "method": "POST"},
                    {"url": "", "method": "GET"},
                ],
            }
        )

        self.assertIsNotNone(adapter)
        self.assertEqual(len(adapter.endpoints), 1)
        self.assertEqual(adapter.endpoints[0].url, "https://example.com/api/articles")

    def test_adapter_round_trip_preserves_endpoint_sources(self):
        adapter = DiscoveryAdapter(
            domain="example.com",
            endpoints=[
                DiscoveryEndpoint(
                    url="https://example.com/api/news",
                    method="GET",
                    source="llm-planner",
                )
            ],
            notes="observed from network",
        )

        restored = adapter_from_dict(adapter_to_dict(adapter))

        self.assertIsNotNone(restored)
        self.assertEqual(restored.domain, "example.com")
        self.assertEqual(restored.notes, "observed from network")
        self.assertEqual(restored.endpoints[0].source, "llm-planner")

    def test_heavy_lock_prevents_parallel_entry_and_cleans_up(self):
        with TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "heavy.lock"
            with DiscoveryHeavyLock(path=lock_path, ttl_seconds=60) as first:
                self.assertTrue(first.acquired)
                with DiscoveryHeavyLock(path=lock_path, ttl_seconds=60) as second:
                    self.assertFalse(second.acquired)
                    self.assertEqual(second.reason, "busy")

            self.assertFalse(lock_path.exists())

    def test_cached_adapter_success_skips_heavy_discovery(self):
        adapter = DiscoveryAdapter(
            domain="example.com",
            endpoints=[DiscoveryEndpoint(url="https://example.com/api/news")],
        )
        candidate = advanced.CandidateEndpoint(
            endpoint_url="https://example.com/api/news",
            discovered_urls=["https://example.com/news/story"],
            score=10,
            detection_method="cached-adapter",
            content_type="application/json",
        )

        with (
            patch.object(advanced, "discover_api_endpoints", return_value=[]),
            patch.object(advanced, "load_cached_adapter", return_value=adapter),
            patch.object(advanced, "execute_adapter", return_value=[candidate]),
            patch.object(advanced, "collect_browser_network_samples") as collect_network,
            patch.object(advanced, "plan_adapter_with_llm") as plan_adapter,
            patch.object(advanced, "is_content_candidate", return_value=True),
        ):
            result = advanced.advanced_discover_content_links("https://example.com")

        collect_network.assert_not_called()
        plan_adapter.assert_not_called()
        self.assertEqual(result.urls, ["https://example.com/news/story"])
        self.assertEqual(result.browser_tracing_status, "cached-skip")
        self.assertEqual(result.llm_status, "cached-only")


if __name__ == "__main__":
    unittest.main()
