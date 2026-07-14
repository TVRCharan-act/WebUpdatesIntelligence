"""Structured OpenAI business-intelligence analysis.

A drop-in alternative to :class:`mysignal.providers.gemini.GeminiAnalyzer` —
same ``analyze()`` signature, same validated :class:`InsightAnalysis` shape, so
``persist_insight`` and the frontend see identical records regardless of which
model produced them.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from backend.app.config import Settings, get_settings
from mysignal.providers.gemini import SYSTEM_INSTRUCTION, InsightAnalysis


class OpenAIOutputError(RuntimeError):
    pass


class OpenAIAnalyzer:
    def __init__(self, settings: Settings | None = None, *, client: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def analyze(self, *, title: str, content: str, source_url: str) -> dict[str, Any]:
        self.settings.require_openai()
        content = content.strip()[:30_000]
        if not content:
            raise OpenAIOutputError("Cannot analyze empty content.")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise OpenAIOutputError("openai is required for OpenAI analysis.") from exc
        client = self._client or OpenAI(api_key=self.settings.openai_api_key)
        prompt = f"TITLE:\n{title}\n\nSOURCE URL:\n{source_url}\n\nCONTENT:\n{content}"
        try:
            response = client.chat.completions.parse(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": prompt},
                ],
                response_format=InsightAnalysis,
            )
            message = response.choices[0].message
            analysis = message.parsed
            raw = message.content
            if analysis is None:
                raise OpenAIOutputError(
                    f"OpenAI returned no structured insight output ({message.refusal or 'empty response'})."
                )
            if not isinstance(analysis, InsightAnalysis):
                analysis = InsightAnalysis.model_validate(analysis)
        except OpenAIOutputError:
            raise
        except (ValidationError, ValueError, TypeError, IndexError) as exc:
            raise OpenAIOutputError("OpenAI returned invalid structured insight output.") from exc
        except Exception as exc:
            raise OpenAIOutputError(f"OpenAI analysis failed: {exc}") from exc
        return {
            "headline": analysis.headline,
            "summary": analysis.summary,
            "business_significance": analysis.business_significance,
            "severity": analysis.severity,
            "confidence": analysis.confidence,
            "relevant": analysis.relevant,
            "model": self.settings.openai_model,
            "raw": raw,
        }
