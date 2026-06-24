from mysignal.monitoring.inventory_store import (
    load_tracked_hubs,
    load_inventory,
    save_inventory,
)

from mysignal.monitoring.inventory_monitor import (
    fetch_inventory,
)

from mysignal.filters.content_filter import (
    is_content_candidate,
)

from mysignal.notifications.smtp_email import (
    send_article_update_email,
)

from mysignal.workflows.inventory import (
    build_inventory_for_hubs,
    find_new_inventory_urls,
)


def process_new_url(
    url,
):
    from mysignal.processors.article_processor import (
        summarize_url,
    )

    return summarize_url(
        url,
    )


def main():

    tracked_hubs = (
        load_tracked_hubs()
    )

    if not tracked_hubs:

        print(
            "No tracked hubs found."
        )

        return

    previous_inventory = (
        load_inventory()
    )

    print()

    print(
        "=" * 60
    )

    print(
        "REBUILDING INVENTORY"
    )

    print(
        "=" * 60
    )

    build = build_inventory_for_hubs(
        tracked_hubs,
        fetch_inventory,
    )

    for hub, urls in build.raw_inventory.items():
        print()
        print(
            f"CHECKING: {hub}"
        )
        print(
            f"FOUND {len(urls)} URLS"
        )

    for error in build.errors:
        print()
        print(
            f"FAILED: {error.hub}"
        )
        print(error.error)

    current_inventory = build.inventory

    print()

    print(
        "=" * 60
    )

    print(
        "CHANGES DETECTED"
    )

    print(
        "=" * 60
    )

    changes = find_new_inventory_urls(
        previous_inventory,
        current_inventory,
        tracked_hubs,
    )
    total_new_urls = sum(
        len(urls)
        for urls in changes.values()
    )

    for hub, new_urls in changes.items():
        print()

        print(
            f"HUB: {hub}"
        )

        print(
            "-" * 40
        )

        for url in sorted(
            new_urls
        ):

            if not is_content_candidate(
                url
            ):
                continue

            print(
                f"NEW: {url}"
            )

            try:

                article = (
                    process_new_url(
                        url
                    )
                )

                print()

                print(
                    "=" * 60
                )

                print(
                    article.title
                )

                print(
                    "=" * 60
                )

                print(
                    article.summary
                )

                try:
                    email_sent = send_article_update_email(
                        article,
                    )

                    if email_sent:
                        print(
                            "EMAIL SENT"
                        )

                except Exception as email_error:
                    print(
                        f"FAILED TO EMAIL: {url}"
                    )
                    print(
                        email_error
                    )

            except Exception as e:

                print(
                    f"FAILED TO PROCESS: "
                    f"{url}"
                )

                print(e)

    if total_new_urls == 0:

        print()

        print(
            "No new URLs found."
        )

    save_inventory(
        current_inventory
    )

    print()

    print(
        "=" * 60
    )

    print(
        "MONITORING COMPLETE"
    )

    print(
        "=" * 60
    )

    print(
        f"NEW URLS FOUND: "
        f"{total_new_urls}"
    )


if __name__ == "__main__":
    main()
