from mysignal.monitoring.inventory_store import (
    load_seen_url_records,
    save_seen_url_records,
)
from mysignal.notifications.smtp_email import (
    send_article_update_email,
)


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

        try:
            email_sent = send_article_update_email(
                article,
                recipients=recipients,
            )

            if email_sent:
                print(
                    "EMAIL SENT",
                )
                if recipients:
                    print(
                        f"RECIPIENTS: {', '.join(recipients)}",
                    )

        except Exception as email_error:
            print(
                f"FAILED TO EMAIL: {url}",
            )
            print(
                email_error,
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
        print(
            f"FAILED TO PROCESS: {url}",
        )
        print(
            exc,
        )

    return False
