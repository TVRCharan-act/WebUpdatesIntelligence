"""Manual acquisition smoke test; it is intentionally not a test-suite module."""

if __name__ == "__main__":
    from mysignal.processors.article_processor import summarize_url

    article = summarize_url("https://example.com")
    print(article.title)
    print(article.summary)
