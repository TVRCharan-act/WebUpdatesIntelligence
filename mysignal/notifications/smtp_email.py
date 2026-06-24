import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

from mysignal.models.article import Article


load_dotenv()
load_dotenv(
    Path(__file__).resolve().parents[1] / ".env",
    override=False,
)


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    username: str | None
    password: str | None
    sender: str
    recipients: list[str]
    use_tls: bool = True
    use_ssl: bool = False


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def load_smtp_config() -> SmtpConfig | None:
    email_address = os.getenv("EMAIL_ADDRESS")
    email_app_password = os.getenv("EMAIL_APP_PASSWORD")
    email_recipient = os.getenv("EMAIL_RECIPIENT")

    host = os.getenv("SMTP_HOST") or (
        "smtp.gmail.com"
        if email_address and email_app_password
        else None
    )
    recipients = [
        recipient.strip()
        for recipient in (
            os.getenv("SMTP_TO")
            or email_recipient
            or ""
        ).split(",")
        if recipient.strip()
    ]

    if not host or not recipients:
        return None

    default_port = "465" if _env_bool("SMTP_USE_SSL", False) else "587"
    port = int(
        os.getenv(
            "SMTP_PORT",
            default_port,
        )
    )
    username = os.getenv("SMTP_USERNAME") or email_address
    password = os.getenv("SMTP_PASSWORD") or email_app_password
    sender = os.getenv("SMTP_FROM") or username

    if not sender:
        raise ValueError("SMTP_FROM, SMTP_USERNAME, or EMAIL_ADDRESS must be set to send email.")

    return SmtpConfig(
        host=host,
        port=port,
        username=username,
        password=password,
        sender=sender,
        recipients=recipients,
        use_tls=_env_bool("SMTP_USE_TLS", True),
        use_ssl=_env_bool("SMTP_USE_SSL", False),
    )


def _headline_from_summary(summary: str | None, fallback: str) -> str:
    if not summary:
        return fallback

    lines = [
        line.strip()
        for line in summary.splitlines()
        if line.strip()
    ]

    for index, line in enumerate(lines):
        if line.upper().rstrip(":") == "HEADLINE" and index + 1 < len(lines):
            return lines[index + 1]

    return fallback


def build_article_update_email(
    article: Article,
    config: SmtpConfig,
) -> EmailMessage:
    headline = _headline_from_summary(
        article.summary,
        article.title,
    )
    subject = f"Website update: {headline}"

    body = "\n".join(
        [
            article.summary or "A new monitored URL was found.",
            "",
            "New URL:",
            article.url,
        ]
    )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.sender
    message["To"] = ", ".join(config.recipients)
    message.set_content(body)

    return message


def send_article_update_email(article: Article) -> bool:
    config = load_smtp_config()

    if config is None:
        print(
            "SMTP email skipped: set EMAIL_ADDRESS, EMAIL_APP_PASSWORD, and EMAIL_RECIPIENT to enable alerts.",
        )
        return False

    message = build_article_update_email(
        article,
        config,
    )

    if config.use_ssl:
        with smtplib.SMTP_SSL(
            config.host,
            config.port,
        ) as server:
            _send_message(
                server,
                config,
                message,
                start_tls=False,
            )
    else:
        with smtplib.SMTP(
            config.host,
            config.port,
        ) as server:
            _send_message(
                server,
                config,
                message,
                start_tls=config.use_tls,
            )

    return True


def _send_message(
    server: smtplib.SMTP,
    config: SmtpConfig,
    message: EmailMessage,
    start_tls: bool,
) -> None:
    if start_tls:
        server.starttls()

    if config.username and config.password:
        server.login(
            config.username,
            config.password,
        )

    server.send_message(message)
