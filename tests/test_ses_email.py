from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mysignal.models.article import Article
from mysignal.notifications.ses_email import send_article_update_email


class SesArticleEmailTests(unittest.TestCase):
    def test_legacy_article_updates_use_ses(self):
        article = Article(
            url="https://example.com/news/important",
            title="Important update",
            markdown="Article body",
            summary="A relevant business update.",
        )
        settings = SimpleNamespace(ses_default_recipients=("alerts@example.com",))

        with (
            patch("mysignal.notifications.ses_email.get_settings", return_value=settings),
            patch("mysignal.notifications.ses_email.SesEmailSender") as sender,
        ):
            sent = send_article_update_email(article)

        self.assertTrue(sent)
        sender.return_value.send.assert_called_once_with(
            {
                "title": article.title,
                "summary": article.summary,
                "discovered_url": article.url,
            },
            ["alerts@example.com"],
        )
