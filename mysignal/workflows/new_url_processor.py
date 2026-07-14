from mysignal.monitoring.inventory_store import (
    load_seen_url_records,
    save_seen_url_records,
)
from mysignal.notifications.ses_email import (
    send_article_update_email,
)

try:
    from backend.app.observability import log_health_event
except Exception:
    log_health_event = None


def summarize_new_url(
    url: str,
):
    from mysignal.processors.article_processor import summarize_url

    return summarize_url(
        url,
    )


def process_new_url_record(
    *,
    url: str,
    record: dict,
    recipients: list[str],
    processing_errors: list[str] | None = None,
    send_email: bool = True,
    email_result: dict | None = None,
) -> bool:
    print()
    print("NEW URL")
    print("-" * 40)
    print(
        url,
    )
    print("TRACE:")
    print(
        " -> ".join(
            record[
                "trace"
            ]
        )
    )

    try:
        article = summarize_new_url(
            url,
        )

        print()
        print("=" * 60)
        print(
            article.title,
        )
        print("=" * 60)
        print(
            article.summary,
        )

        if send_email:
            try:
                email_sent = send_article_update_email(
                    article,
                    recipients=recipients,
                )

                if email_result is not None:
                    email_result["status"] = "sent" if email_sent else "skipped"
                    email_result["error"] = None if email_sent else "SES is not configured or no recipients are enabled."

                if email_sent:
                    print(
                        "EMAIL SENT",
                    )
                    if recipients:
                        print(
                            f"RECIPIENTS: {', '.join(recipients)}",
                        )
                else:
                    print(
                        "EMAIL SKIPPED",
                    )

            except Exception as email_error:
                if email_result is not None:
                    email_result["status"] = "failed"
                    email_result["error"] = str(email_error)

                print(
                    f"FAILED TO EMAIL: {url}",
                )
                print(
                    email_error,
                )
                if log_health_event:
                    log_health_event(
                        event_type="email",
                        service="celery-worker",
                        action="send_article_update_email",
                        status="error",
                        metadata={
                            "url": url,
                            "error": str(email_error),
                            "error_type": type(email_error).__name__,
                        },
                    )
        else:
            if email_result is not None:
                email_result["status"] = "pending"
                email_result["error"] = None
            print(
                "EMAIL QUEUED FOR MANUAL APPROVAL",
            )

        records = load_seen_url_records()
        records[
            url
        ] = record
        save_seen_url_records(
            records,
        )

        return True

    except Exception as exc:
        error_message = str(exc)
        print(
            f"FAILED TO PROCESS: {url}",
        )
        print(
            exc,
        )
        if processing_errors is not None:
            processing_errors.append(error_message)
        if log_health_event:
            log_health_event(
                event_type="url_processing",
                service="celery-worker",
                action="process_new_url",
                status="error",
                metadata={
                    "url": url,
                    "error": error_message,
                    "error_type": type(exc).__name__,
                },
            )

    return False
