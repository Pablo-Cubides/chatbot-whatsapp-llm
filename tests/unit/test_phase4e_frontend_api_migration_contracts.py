"""Phase 4E contracts for centralized frontend API usage on protected pages."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]

MIGRATED_PAGES = [
    "ui/analytics.html",
    "ui/alerts.html",
    "ui/business_config.html",
    "ui/calendar_config.html",
    "ui/chat.html",
    "ui/index.html",
    "ui/setup.html",
]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("rel_path", MIGRATED_PAGES)
def test_migrated_pages_do_not_use_legacy_manual_auth_headers(rel_path: str) -> None:
    text = _read(rel_path)

    assert "sessionStorage.getItem('token')" not in text
    assert "Authorization" not in text


@pytest.mark.parametrize("rel_path", MIGRATED_PAGES)
def test_migrated_pages_avoid_direct_api_fetch_calls(rel_path: str) -> None:
    text = _read(rel_path)

    assert "fetch('/api/" not in text
    assert 'fetch("/api/' not in text
