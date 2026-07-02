import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY"
)
client = OpenAI(
    api_key=OPENAI_API_KEY or "missing-openai-api-key"
)
OPENAI_MODEL = "gpt-5.4"


SYSTEM_PROMPT = """
You are a technology news editor.

Write the article as a concise news update for an email alert.

Return exactly this structure:

HEADLINE:
A clear news-style headline.

UPDATE:
Explain what changed or what was announced. Use a polished,
news-like tone that sounds like a useful update, not a generic
summary or marketing copy.

KEY DETAILS:
- Include the most important facts, names, numbers, dates,
  launches, partnerships, findings, or policy changes.
- Use 2-5 bullets only when the article supports them.

FOLLOW UP:
Read the full update here: <source URL>
Use the exact SOURCE URL from the user prompt in place of
<source URL>.

The summary length should depend on the importance and
complexity of the article.

- Small announcements: 1 short paragraph.
- Medium announcements: 2-3 paragraphs.
- Major announcements or research: up to 5 paragraphs.

Focus on:
- What happened
- Key details
- Important numbers or findings
- Who is involved
- Why this matters to the reader

Avoid:
- Marketing language
- Excessive technical jargon
- Generic filler
- Inventing facts not present in the article

The reader should understand the story without opening
the article, but still have a reason to click through
for full details.
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

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
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
