from mysignal.models.article import (
    Article,
)

from mysignal.collector.firecrawl_collector import (
    scrape_article,
)

from mysignal.summarizers.openai_summarizer import (
    summarize_article,
)

def build_article(
    url: str,
) -> Article:

    result = scrape_article(
        url
    )
    print(type(result))

    print(result)

    markdown = ""

    title = url

    #
    # Firecrawl SDK versions differ
    #
    if isinstance(
        result,
        dict,
    ):

        markdown = (
            result.get(
                "markdown",
                ""
            )
        )

        metadata = (
            result.get(
                "metadata",
                {}
            )
        )

        title = (
            metadata.get(
                "title",
                url,
            )
        )

    else:

        markdown = getattr(
            result,
            "markdown",
            "",
        )

        metadata = getattr(
            result,
            "metadata",
            None,
        )

        if metadata:

            title = getattr(
                metadata,
                "title",
                url,
            )

        else:

            title = url

    return Article(
        url=url,
        title=title,
        markdown=markdown,
    )
    
def summarize_url(
    url: str,
) -> Article:

    article = (
        build_article(
            url
        )
    )
    print()
    print("=" * 80)
    print("TITLE")
    print("=" * 80)
    print(article.title)

    print()
    print("=" * 80)
    print("MARKDOWN PREVIEW")
    print("=" * 80)
    print(article.markdown[:2000])
    article.summary = (
        summarize_article(
            article.title,
            article.markdown,
            source_url=article.url,
        )
    )

    return article
