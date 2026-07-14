"""Compatibility helpers backed by the current acquisition/Gemini pipeline."""

from mysignal.models.article import Article
from mysignal.providers.gemini import GeminiAnalyzer
from mysignal.providers.pipeline import acquire_content


def build_article(url: str) -> Article:
    content = acquire_content(url, "auto")
    return Article(url=url, title=content.title, markdown=content.text)


def summarize_url(url: str) -> Article:
    article = build_article(url)
    analysis = GeminiAnalyzer().analyze(title=article.title, content=article.markdown, source_url=url)
    article.title = str(analysis["headline"])
    article.summary = str(analysis["summary"])
    return article
