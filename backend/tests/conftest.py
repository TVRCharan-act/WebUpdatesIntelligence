"""Shared fixtures for the backend test suite.

Every test runs against the in-memory storage double so the suite needs no S3,
no AWS credentials, and no network access. The double shares the exact key
layout used by the S3 backend, so key-level assertions (e.g. "no object left in
the bucket") stay meaningful.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from backend.app.repository import S3Repository
from backend.app.storage import InMemoryJsonStorage


@pytest.fixture
def storage() -> InMemoryJsonStorage:
    return InMemoryJsonStorage()


@pytest.fixture
def repo(storage: InMemoryJsonStorage) -> S3Repository:
    return S3Repository(storage, prefix="test")


@pytest.fixture
def owner(repo: S3Repository) -> str:
    name = "acme"
    repo.create_account(name, "hash", "customer")
    return name


def make_source(repo: S3Repository, owner: str, *, baseline: bool = True) -> dict[str, Any]:
    """Create a company + source, optionally past the one-time baseline phase."""
    company = repo.create_company(owner, "Globex", "high")
    source = repo.create_source(
        owner, {"company_id": int(company["id"]), "url": "https://globex.example/news"}
    )
    if baseline:
        source = repo.update_source(
            int(source["id"]), owner, baseline_completed_at="2026-01-01T00:00:00+00:00"
        )
    return source


class FakeContent(SimpleNamespace):
    """Stand-in for the acquisition provider's returned content object."""


class FakeCandidate(SimpleNamespace):
    """Stand-in for a discovered candidate URL."""


class FakeAnalyzer:
    """Analyzer double that always returns a relevant insight."""

    def analyze(self, *, title: str, content: str, source_url: str) -> dict[str, Any]:
        return {
            "relevant": True,
            "headline": f"Insight for {source_url}",
            "summary": "A relevant change was detected.",
            "model": "fake",
            "severity": "high",
            "confidence": "high",
            "raw": {"title": title, "content": content},
        }
