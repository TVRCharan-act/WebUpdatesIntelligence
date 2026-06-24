import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv(
        "OPENAI_API_KEY"
    )
)


SYSTEM_PROMPT = """
You are a technology news editor.

Summarize the article as a news briefing.

Return:

HEADLINE:
A clear news headline.

SUMMARY:
Explain the announcement, findings, launch, partnership,
research result, or policy change.

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

Avoid:
- Marketing language
- Excessive technical jargon
- Generic filler

The reader should understand the story without opening
the article, but still have a reason to click through
for full details.
"""


def summarize_article(
    title: str,
    content: str,
) -> str:

    MAX_CHARS = 15000

    content = content[:MAX_CHARS]

    user_prompt = f"""
TITLE:
{title}

ARTICLE:
{content}
"""

    response = client.chat.completions.create(
        model="gpt-5.4",
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