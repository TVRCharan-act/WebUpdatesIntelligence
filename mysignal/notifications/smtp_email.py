"""Deprecated compatibility facade for the former SMTP module.

All notification delivery now uses Amazon SES. Existing command-line imports
remain valid during the transition, but no SMTP connection is created.
"""

from mysignal.notifications.ses_email import EmailDeliveryError, send_article_update_email


SmtpDeliveryError = EmailDeliveryError

__all__ = ["SmtpDeliveryError", "send_article_update_email"]
