def categorize_url(
    url: str,
):
    lowered = url.lower()

    if "research" in lowered:
        return "research"

    if (
        "publication" in lowered
        or "journal" in lowered
        or "whitepaper" in lowered
    ):
        return "publications"

    if (
        "blog" in lowered
        or "insight" in lowered
    ):
        return "blog"

    if (
        "story" in lowered
        or "stories" in lowered
    ):
        return "stories"

    if (
        "news" in lowered
        or "press" in lowered
        or "newsroom" in lowered
        or "announcement" in lowered
        or "update" in lowered
    ):
        return "news"

    if "media" in lowered:
        return "media"

    return "other"