"""Parsing for the analyst-brief output format.

The summarizer returns a small labeled structure:

    HEADLINE:
    <headline>

    SUMMARY:
    <one flowing paragraph — significance woven into the prose, no sub-sections>

    SEVERITY:
    <low | medium | high>

    CONFIDENCE:
    <low | medium | high>

This module has no third-party imports so it can be used (and unit-tested)
without loading the OpenAI client. It is tolerant of the older
HEADLINE/UPDATE/KEY DETAILS/FOLLOW UP format and of unlabeled text.
"""

from __future__ import annotations

import re

VALID_SEVERITY = {"low", "medium", "high"}
VALID_CONFIDENCE = {"low", "medium", "high"}

DEFAULT_SEVERITY = "medium"
DEFAULT_CONFIDENCE = "medium"

# Body labels, in the order we prefer to source the paragraph from.
_BODY_LABELS = ("SUMMARY", "UPDATE")
# Every label we recognise (older formats included) so we can slice cleanly.
_ALL_LABELS = (
    "HEADLINE",
    "SUMMARY",
    "UPDATE",
    "KEY DETAILS",
    "FOLLOW UP",
    "SEVERITY",
    "CONFIDENCE",
)

_LABEL_RE = re.compile(
    r"(?im)^[ \t]*(" + "|".join(re.escape(label) for label in _ALL_LABELS) + r")[ \t]*:[ \t]*"
)


def _split_sections(raw: str) -> dict[str, str]:
    matches = list(_LABEL_RE.finditer(raw))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        label = match.group(1).upper()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        sections[label] = raw[start:end].strip()
    return sections


def _first_word(value: str) -> str:
    stripped = value.strip().lower()
    if not stripped:
        return ""
    return re.split(r"[^a-z]+", stripped, maxsplit=1)[0]


def parse_insight_output(raw: str | None) -> dict[str, object]:
    """Return ``{headline, body, severity, confidence}`` from raw model output.

    Always returns a usable body: falls back to the whole text when no known
    labels are present, so nothing is ever dropped.
    """
    if not raw or not raw.strip():
        return {
            "headline": None,
            "body": "",
            "severity": DEFAULT_SEVERITY,
            "confidence": DEFAULT_CONFIDENCE,
        }

    sections = _split_sections(raw)

    headline = None
    if sections.get("HEADLINE"):
        first_line = sections["HEADLINE"].splitlines()[0].strip()
        headline = first_line or None

    body = ""
    for label in _BODY_LABELS:
        if sections.get(label):
            body = sections[label].strip()
            break
    if not body:
        if sections:
            # Recognised labels but no body label — join everything that isn't meta.
            leftover = [
                text
                for label, text in sections.items()
                if label not in ("HEADLINE", "SEVERITY", "CONFIDENCE") and text
            ]
            body = "\n\n".join(leftover).strip() or raw.strip()
        else:
            body = raw.strip()

    severity = _first_word(sections.get("SEVERITY", ""))
    confidence = _first_word(sections.get("CONFIDENCE", ""))

    return {
        "headline": headline,
        "body": body,
        "severity": severity if severity in VALID_SEVERITY else DEFAULT_SEVERITY,
        "confidence": confidence if confidence in VALID_CONFIDENCE else DEFAULT_CONFIDENCE,
    }
