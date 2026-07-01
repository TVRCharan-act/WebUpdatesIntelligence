import unittest

from mysignal.discovery.api_discovery import (
    detect_frameworks_from_html,
    detect_frameworks_from_javascript,
    framework_probe_urls,
    normalize_endpoint_candidate,
    same_origin_script_urls,
)


class TraceJsDiscoveryTests(unittest.TestCase):
    def test_script_urls_use_final_page_url_as_resolution_base(self):
        html = """
        <html>
          <head>
            <script src="main.mjs#version"></script>
            <link rel="modulepreload" href="./chunks/runtime.cjs?cache=1">
          </head>
          <body>
            <script>import("/static/app.js#loader")</script>
          </body>
        </html>
        """

        urls = same_origin_script_urls(
            html,
            "https://example.com/newsroom",
            base_url="https://example.com/newsroom/",
        )

        self.assertEqual(
            urls,
            [
                "https://example.com/newsroom/main.mjs",
                "https://example.com/newsroom/chunks/runtime.cjs?cache=1",
                "https://example.com/static/app.js",
            ],
        )

    def test_endpoint_candidates_use_final_page_url_as_resolution_base(self):
        urls = normalize_endpoint_candidate(
            "api/articles.json",
            page_url="https://example.com/newsroom",
            page_base_url="https://example.com/newsroom/",
            script_url="https://example.com/assets/app.js",
        )

        self.assertEqual(
            urls,
            [
                "https://example.com/assets/api/articles.json",
                "https://example.com/newsroom/api/articles.json",
            ],
        )


class FrameworkRegistryTests(unittest.TestCase):
    def test_framework_detection_uses_registered_html_and_generator_markers(self):
        html = """
        <html>
          <head>
            <meta name="generator" content="Gatsby">
          </head>
          <body data-api="/wp-json/wp/v2/posts"></body>
        </html>
        """

        self.assertEqual(
            detect_frameworks_from_html(
                html,
            ),
            {
                "gatsby",
                "wordpress",
            },
        )

    def test_framework_detection_uses_registered_javascript_markers(self):
        javascript = "const api = '@tryghost/content-api'; fetch('/ghost/api');"

        self.assertEqual(
            detect_frameworks_from_javascript(
                javascript,
            ),
            {
                "ghost",
            },
        )

    def test_framework_probe_urls_use_registered_probe_paths(self):
        probes = framework_probe_urls(
            "https://example.com/newsroom",
            {
                "ghost",
                "wordpress",
            },
            [],
        )

        self.assertIn(
            (
                "https://example.com/wp-json/wp/v2/posts",
                "wordpress-rest-probe",
            ),
            probes,
        )
        self.assertIn(
            (
                "https://example.com/ghost/api/content/posts",
                "ghost-content-probe",
            ),
            probes,
        )


if __name__ == "__main__":
    unittest.main()
