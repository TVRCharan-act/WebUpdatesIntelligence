"""Admin-only side-by-side crawler comparison (ZenRows vs Crawl4AI).

Runs the same acquisition/discovery code paths the real monitoring pipeline
uses (:mod:`mysignal.providers.pipeline`) against one admin-supplied URL for
both providers, so the comparison reflects exactly what a customer's monitor
would experience with each crawler — not a separate, parallel implementation.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.config import get_settings
from mysignal.providers.pipeline import acquire_content, discover_candidates

PROVIDERS = ("zenrows", "crawl4ai")


def _run_discovery(url: str, provider: str) -> dict[str, Any]:
    started = perf_counter()
    fake_source = {"strategy": "parent", "url": url, "acquisition_provider": provider, "trace_js": False}
    try:
        candidates = discover_candidates(fake_source)
        return {
            "success": True,
            "latency_seconds": round(perf_counter() - started, 3),
            "link_count": len(candidates),
            "sample_links": [candidate.url for candidate in candidates[:10]],
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "latency_seconds": round(perf_counter() - started, 3),
            "link_count": 0,
            "sample_links": [],
            "error": str(exc),
        }


def _run_content(url: str, provider: str) -> dict[str, Any]:
    started = perf_counter()
    try:
        content = acquire_content(url, provider)
        return {
            "success": True,
            "latency_seconds": round(perf_counter() - started, 3),
            "title": content.title,
            "length": len(content.text),
            "snippet": content.text[:500],
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "latency_seconds": round(perf_counter() - started, 3),
            "title": None,
            "length": 0,
            "snippet": None,
            "error": str(exc),
        }


def run_provider(url: str, provider: str) -> dict[str, Any]:
    started = perf_counter()
    discovery = _run_discovery(url, provider)
    content = _run_content(url, provider)
    ok = discovery["success"] or content["success"]
    return {
        "provider": provider,
        "success": ok,
        "error": None if ok else (content["error"] or discovery["error"]),
        "total_latency_seconds": round(perf_counter() - started, 3),
        "discovery": discovery,
        "content": content,
    }


def compare_providers(url: str) -> list[dict[str, Any]]:
    """Run every provider concurrently so the wall-clock cost is one run, not the sum."""
    with ThreadPoolExecutor(max_workers=len(PROVIDERS)) as pool:
        futures = {provider: pool.submit(run_provider, url, provider) for provider in PROVIDERS}
        return [futures[provider].result() for provider in PROVIDERS]


class CrawlerJudgeVerdict(BaseModel):
    winner: Literal["zenrows", "crawl4ai", "tie"]
    reasoning: str = Field(min_length=1, max_length=2000)
    zenrows_notes: str = Field(min_length=1, max_length=1000)
    crawl4ai_notes: str = Field(min_length=1, max_length=1000)


_JUDGE_SYSTEM_INSTRUCTION = """You are a pragmatic web-scraping infrastructure reviewer. You are shown the
results of two crawler pipelines (ZenRows and Crawl4AI) run against the same URL for a website-change
monitoring product. Decide which pipeline a production monitor should prefer for THIS specific URL.
Weigh reliability and content completeness over raw speed; a fast failure is worse than a slower success.
If the two are genuinely equivalent, say 'tie'. Keep each notes field to one or two sentences."""


def _judge_prompt(url: str, results: list[dict[str, Any]]) -> str:
    lines = [f"URL being crawled: {url}", ""]
    for result in results:
        discovery, content = result["discovery"], result["content"]
        lines.append(f"=== {result['provider'].upper()} ===")
        lines.append(f"Overall success: {result['success']}")
        lines.append(
            f"Discovery: success={discovery['success']} latency={discovery['latency_seconds']}s "
            f"links_found={discovery['link_count']} error={discovery['error']}"
        )
        lines.append(
            f"Content: success={content['success']} latency={content['latency_seconds']}s "
            f"length={content['length']} title={content['title']!r} error={content['error']}"
        )
        if content.get("snippet"):
            lines.append(f"Content snippet: {content['snippet'][:400]}")
        lines.append("")
    lines.append(
        "Based on success, latency, content completeness, and link-discovery breadth, decide which "
        "crawler pipeline performed better for this specific URL."
    )
    return "\n".join(lines)


def _empty_verdict(*, model: str | None, error: str) -> dict[str, Any]:
    return {
        "available": False,
        "model": model,
        "error": error,
        "winner": None,
        "reasoning": None,
        "zenrows_notes": None,
        "crawl4ai_notes": None,
    }


def judge_crawlers(url: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    """Ask whichever LLM is configured to pick a winner. Never raises — a judging
    failure degrades to an 'unavailable' verdict so the comparison itself still renders."""
    settings = get_settings()
    prompt = _judge_prompt(url, results)

    if settings.openai_api_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.parse(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": _JUDGE_SYSTEM_INSTRUCTION},
                    {"role": "user", "content": prompt},
                ],
                response_format=CrawlerJudgeVerdict,
            )
            parsed = response.choices[0].message.parsed
            if parsed is None:
                raise RuntimeError("The model returned no structured verdict.")
            return {"available": True, "model": settings.openai_model, "error": None, **parsed.model_dump()}
        except Exception as exc:
            return _empty_verdict(model=settings.openai_model, error=f"OpenAI judge failed: {exc}")

    if settings.google_api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.google_api_key)
            response = client.models.generate_content(
                model=settings.google_gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_JUDGE_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=CrawlerJudgeVerdict,
                ),
            )
            parsed = getattr(response, "parsed", None)
            if parsed is None:
                parsed = CrawlerJudgeVerdict.model_validate(json.loads(response.text or ""))
            elif not isinstance(parsed, CrawlerJudgeVerdict):
                parsed = CrawlerJudgeVerdict.model_validate(parsed)
            return {"available": True, "model": settings.google_gemini_model, "error": None, **parsed.model_dump()}
        except Exception as exc:
            return _empty_verdict(model=settings.google_gemini_model, error=f"Gemini judge failed: {exc}")

    return _empty_verdict(model=None, error="No OpenAI or Gemini API key is configured for judging.")
