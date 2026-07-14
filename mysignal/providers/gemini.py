"""Structured Gemini business-intelligence analysis."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from backend.app.config import Settings, get_settings


class GeminiOutputError(RuntimeError):
    pass


class InsightAnalysis(BaseModel):
    headline: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=8000)
    business_significance: str = Field(min_length=1, max_length=4000)
    severity: Literal["low", "medium", "high"]
    confidence: Literal["low", "medium", "high"]
    relevant: bool

    @field_validator("headline", "summary", "business_significance")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Text cannot be blank.")
        return value


SYSTEM_INSTRUCTION = """You are a concise business-intelligence analyst. Analyze only the provided content.
Return JSON that conforms to the requested schema. Keep the summary to a focused analyst paragraph. Severity and confidence must be low, medium, or high. Set relevant false for routine, non-material content."""


class GeminiAnalyzer:
    def __init__(self, settings: Settings | None = None, *, client: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def analyze(self, *, title: str, content: str, source_url: str) -> dict[str, Any]:
        self.settings.require_gemini()
        content = content.strip()[:30_000]
        if not content:
            raise GeminiOutputError("Cannot analyze empty content.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise GeminiOutputError("google-genai is required for Gemini analysis.") from exc
        client = self._client or genai.Client(api_key=self.settings.google_api_key)
        prompt = f"TITLE:\n{title}\n\nSOURCE URL:\n{source_url}\n\nCONTENT:\n{content}"
        try:
            response = client.models.generate_content(
                model=self.settings.google_gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=InsightAnalysis,
                ),
            )
            parsed = getattr(response, "parsed", None)
            raw = getattr(response, "text", None)
            if parsed is None:
                parsed = json.loads(raw or "")
            analysis = parsed if isinstance(parsed, InsightAnalysis) else InsightAnalysis.model_validate(parsed)
        except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise GeminiOutputError("Gemini returned invalid structured insight output.") from exc
        except Exception as exc:
            raise GeminiOutputError(f"Gemini analysis failed: {exc}") from exc
        return {
            "headline": analysis.headline,
            "summary": analysis.summary,
            "business_significance": analysis.business_significance,
            "severity": analysis.severity,
            "confidence": analysis.confidence,
            "relevant": analysis.relevant,
            "model": self.settings.google_gemini_model,
            "raw": raw,
        }
