from urllib.parse import urlparse


POSITIVE_TERMS = {

    "news",
    "blog",
    "blogs",

    "research",

    "press",
    "press-release",
    "press-releases",

    "media",
    "media-center",
    "media-room",

    "publication",
    "publications",

    "announcement",
    "announcements",

    "article",
    "articles",

    "insight",
    "insights",

    "story",
    "stories",

    "update",
    "updates",

    "newsroom",

    "journal",
    "journals",

    "whitepaper",
    "whitepapers",

    "case-study",
    "case-studies",
}


NEGATIVE_TERMS = {

    "career",
    "careers",
    "job",
    "jobs",

    "privacy",
    "legal",
    "cookie",

    "support",
    "help",

    "contact",

    "login",
    "signup",
    "register",

    "pricing",

    "docs",
    "documentation",

    "api",

    "about",

    "terms",

    "security",

    "partners",

    "customer-stories",
}


EXCLUDED_EXTENSIONS = (

    ".xml",

    ".pdf",

    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",

    ".zip",
    ".csv",
    ".xlsx",
    ".docx",
)



def normalize_url(
    url: str,
):
    parsed = urlparse(url)

    path = parsed.path.rstrip("/")

    return (
        f"{parsed.scheme}://"
        f"{parsed.netloc}"
        f"{path}"
    )
    
def is_content_url(
    url: str,
):
    lowered = url.lower()

    if lowered.endswith(
        EXCLUDED_EXTENSIONS
    ):
        return False

    if any(
        term in lowered
        for term in NEGATIVE_TERMS
    ):
        return False

    if any(
        term in lowered
        for term in POSITIVE_TERMS
    ):
        return True

    return False

HUB_TERMS = {

    "news",
    "blog",
    "research",

    "press",

    "media",

    "publication",
    "publications",

    "stories",

    "announcement",
    "announcements",

    "newsroom",

}

def is_hub_url(
    url: str,
):
    lowered = url.lower()

    return any(
        term in lowered
        for term in HUB_TERMS
    )