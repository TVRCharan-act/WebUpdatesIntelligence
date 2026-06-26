from urllib.parse import urlparse


BLOCKED_EXTENSIONS = {

    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".svg",

    ".css",
    ".js",

    ".woff",
    ".woff2",

    ".ico",

    ".pdf",
    ".json",
    ".xml",
    ".ics",

}


def is_content_candidate(
    url: str,
) -> bool:

    lowered = url.lower()

    parsed = urlparse(
        lowered
    )

    path = parsed.path

    for extension in (
        BLOCKED_EXTENSIONS
    ):

        if path.endswith(
            extension
        ):
            return False

    return True
