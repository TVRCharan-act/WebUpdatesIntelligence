import os

from firecrawl import (
    FirecrawlApp,
)

from dotenv import (
    load_dotenv,
)

load_dotenv()

app = FirecrawlApp(
    api_key=os.getenv(
        "fire_crawler_api"
    )
)


def scrape_article(
    url: str,
):
    result = app.scrape_url(
        url,
        formats=[
            "markdown",
        ],
    )

    return result