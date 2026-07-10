import contextvars
import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# The analytical lens for the current summarization, set per source run based on
# what the sentinel is posted to watch (company.watch_type). This shapes what the
# analyst treats as significant. Set via set_watch_lens() by monitor_service.
_watch_lens: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "watch_lens", default=None
)


def set_watch_lens(value: str | None) -> None:
    _watch_lens.set(value)


LENS_BY_TYPE = {
    "competitor": (
        "CONTEXT: This page belongs to a COMPETITOR the reader tracks. Read it "
        "through a competitive lens — give the most weight to pricing changes, "
        "product launches, positioning or messaging shifts, partnerships, and "
        "hiring or expansion signals, and make clear whether a change is a threat "
        "or an opportunity. Raise severity for material competitive moves."
    ),
    "industry": (
        "CONTEXT: This page is an INDUSTRY or MARKET source the reader follows for "
        "awareness. Emphasize trends, regulatory or policy changes, and "
        "market-moving developments relevant to someone tracking this space, "
        "rather than routine site activity."
    ),
    "own": (
        "CONTEXT: This page belongs to the reader's OWN organization. Read it "
        "through an integrity lens — an unexpected, removed, or altered piece of "
        "content is itself the story. Call out anything that looks unintended, "
        "off-brand, or like a regression, and raise severity when a change appears "
        "accidental or damaging."
    ),
}

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY"
)
client = OpenAI(
    api_key=OPENAI_API_KEY or "missing-openai-api-key"
)
OPENAI_MODEL = "gpt-5.4"


SYSTEM_PROMPT = """
You are a sharp business intelligence analyst.

A web page that the reader monitors has changed. Brief them the way a trusted
analyst would: plainly, specifically, and without filler.

Return EXACTLY this structure and nothing else:

HEADLINE:
A clear, specific, news-style headline. No trailing period.

SUMMARY:
A single flowing paragraph, usually 2-5 sentences. Explain what changed and,
in the same prose, why it is significant and what it means for the reader.
Do NOT use bullet points, lists, section labels, or headings inside the
paragraph. Do NOT write signpost phrases like "why it matters", "business
impact", or "recommended action" — weave the significance and any implication
naturally into the narrative so it is simply felt when read. Write in a
confident, concise, slightly dry analyst voice. Prefer concrete facts, names,
numbers, and dates over adjectives. Never invent details that are not supported
by the article. Let the length follow the importance of the change: minor
updates get one or two sentences; major developments get a fuller paragraph.

SEVERITY:
One word — low, medium, or high — for how much this change should matter to the
reader.
- high: material moves such as pricing changes, product launches, leadership or
  policy changes, security or legal developments, or anything needing a timely
  response.
- medium: notable but not urgent developments worth being aware of.
- low: minor, cosmetic, or routine updates.

CONFIDENCE:
One word — low, medium, or high — for how confident you are that this is a real,
meaningful change and that your reading of it is accurate given the available
content.
"""


def summarize_article(
    title: str,
    content: str,
    source_url: str | None = None,
) -> str:

    MAX_CHARS = 15000

    content = content[:MAX_CHARS]

    user_prompt = f"""
TITLE:
{title}

SOURCE URL:
{source_url or title}

ARTICLE:
{content}
"""

    lens = LENS_BY_TYPE.get(_watch_lens.get() or "")
    system_content = f"{SYSTEM_PROMPT}\n\n{lens}" if lens else SYSTEM_PROMPT

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_content,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    )

    return (
        response
        .choices[0]
        .message
        .content
    )
