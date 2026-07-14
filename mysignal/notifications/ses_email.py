"""AWS SES delivery for analyst-style monitoring alerts."""

from __future__ import annotations

from html import escape
from typing import Any

from backend.app.config import ConfigurationError, Settings, get_settings
from mysignal.models.article import Article


class EmailDeliveryError(RuntimeError):
    pass


def render_insight_email(insight: dict[str, Any]) -> tuple[str, str, str]:
    headline = str(insight.get("title") or "New monitored update")
    summary = str(insight.get("summary") or "A new monitored update is available.")
    source_url = str(insight.get("discovered_url") or "")
    subject = f"Sentinel Actalyst: {headline}"
    text = f"{headline}\n\n{summary}\n\nSource: {source_url}"
    html = "".join(
        (
            "<html><body style='font-family:Arial,sans-serif;line-height:1.5;color:#17323a'>",
            f"<h2>{escape(headline)}</h2>",
            f"<p>{escape(summary)}</p>",
            f"<p><a href='{escape(source_url, quote=True)}'>View monitored update</a></p>",
            "<hr><p style='color:#5c6f75;font-size:12px'>Sentinel Actalyst intelligence alert</p>",
            "</body></html>",
        )
    )
    return subject, text, html


class SesEmailSender:
    def __init__(self, settings: Settings | None = None, *, client: Any | None = None) -> None:
        self.settings = settings or get_settings()
        if client is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover - dependency guard
                raise EmailDeliveryError("boto3 is required for SES email delivery.") from exc
            client = boto3.client("sesv2", region_name=self.settings.ses_region)
        self.client = client

    def send(self, insight: dict[str, Any], recipients: list[str]) -> str:
        try:
            self.settings.require_ses()
        except ConfigurationError as exc:
            raise EmailDeliveryError(str(exc)) from exc
        if not recipients:
            raise EmailDeliveryError("No enabled recipients are configured for this company.")
        subject, text, html = render_insight_email(insight)
        request: dict[str, Any] = {
            "FromEmailAddress": self.settings.email_sender,
            "Destination": {"ToAddresses": sorted(set(recipients))},
            "Content": {
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": text, "Charset": "UTF-8"},
                        "Html": {"Data": html, "Charset": "UTF-8"},
                    },
                }
            },
        }
        if self.settings.ses_configuration_set:
            request["ConfigurationSetName"] = self.settings.ses_configuration_set
        try:
            response = self.client.send_email(**request)
        except Exception as exc:
            raise EmailDeliveryError(f"SES delivery failed: {exc}") from exc
        return str(response.get("MessageId") or "")


def send_article_update_email(
    article: Article,
    recipients: list[str] | str | None = None,
) -> bool:
    """Send a legacy command-line article update through SES.

    The FastAPI application stores recipients per company. This adapter keeps
    the older command-line monitor usable with explicit recipients or the
    ``SES_DEFAULT_RECIPIENTS`` environment setting, without retaining SMTP.
    """
    settings = get_settings()
    resolved_recipients = (
        [item.strip() for item in recipients.split(",") if item.strip()]
        if isinstance(recipients, str)
        else [item.strip() for item in recipients or [] if item.strip()]
    ) or list(settings.ses_default_recipients)
    if not resolved_recipients:
        return False
    SesEmailSender(settings).send(
        {
            "title": article.title,
            "summary": article.summary,
            "discovered_url": article.url,
        },
        resolved_recipients,
    )
    return True
