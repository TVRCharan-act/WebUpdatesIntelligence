from pathlib import Path
import sys


ROOT_DIR = Path(
    __file__,
).resolve().parents[1]

if str(
    ROOT_DIR,
) not in sys.path:
    sys.path.insert(
        0,
        str(
            ROOT_DIR,
        ),
    )

from mysignal.monitoring.inventory_store import (
    load_tracked_recursive_roots,
)
from mysignal.workflows.parent_monitor import (
    discover_new_urls_from_parents,
)
from mysignal.monitoring.inventory_store import (
    load_tracked_recursive_roots,
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


def main() -> None:
    tracked_parents = load_tracked_recursive_roots()

    if not tracked_parents:
        print(
            "No tracked parent URLs found. Run scripts/explore_setup.py first.",
        )
        return

    new_urls, new_records = discover_new_urls_from_parents(
        tracked_parents,
        store_new_urls=False,
    )

    print()
    print("PARENT URL MONITORING COMPLETE")
    print("=" * 60)
    print(
        f"TRACKED PARENTS: {len(tracked_parents)}",
    )
    print(
        f"NEW URLS FOUND: {len(new_urls)}",
    )

    for url in new_urls:
        record = new_records[
            url
        ]

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
                )

                if email_sent:
                    print(
                        "EMAIL SENT",
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

        except Exception as exc:
            print(
                f"FAILED TO PROCESS: {url}",
            )
            print(
                exc,
            )


if __name__ == "__main__":
    main()
