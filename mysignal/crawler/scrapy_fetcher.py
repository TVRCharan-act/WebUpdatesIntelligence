from dataclasses import dataclass
import base64
import json
import subprocess
import sys


@dataclass(frozen=True)
class ScrapyFetchResult:
    url: str
    status: int
    text: str
    body: bytes


def fetch_urls(
    urls: list[str],
) -> list[ScrapyFetchResult]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "mysignal.crawler.scrapy_fetch_worker",
        ],
        input=json.dumps(
            {
                "urls": urls,
            }
        ),
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            completed.stderr.strip()
            or completed.stdout.strip()
            or "Scrapy worker failed.",
        )

    payload = json.loads(
        completed.stdout,
    )
    errors = payload.get(
        "errors",
        [],
    )

    if errors and not payload.get(
        "results",
    ):
        raise RuntimeError(
            errors[0],
        )

    return [
        ScrapyFetchResult(
            url=result[
                "url"
            ],
            status=result[
                "status"
            ],
            text=result[
                "text"
            ],
            body=base64.b64decode(
                result[
                    "body"
                ]
            ),
        )
        for result in payload.get(
            "results",
            [],
        )
    ]


def fetch_url(
    url: str,
) -> ScrapyFetchResult:
    results = fetch_urls(
        [
            url,
        ]
    )

    if not results:
        raise RuntimeError(
            f"Scrapy failed to fetch the page: {url}",
        )

    return results[0]
