"""Phase 4F contracts for explicit auth-guard consistency on protected pages."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]

PROTECTED_PAGES = [
    "ui/analytics.html",
    "ui/alerts.html",
    "ui/business_config.html",
    "ui/calendar_config.html",
    "ui/chat.html",
    "ui/realtime_dashboard.html",
    "ui/index.html",
    "ui/setup.html",
]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("rel_path", PROTECTED_PAGES)
def test_protected_pages_keep_runtime_scripts_and_explicit_guard(rel_path: str) -> None:
    text = _read(rel_path)

    assert '<script src="/ui/auth.js"></script>' in text
    assert '<script src="/ui/api.js"></script>' in text
    assert "requireAuth('/ui/login.html')" in text


def test_login_page_does_not_require_auth_guard() -> None:
    text = _read("ui/login.html")

    assert "requireAuth('/ui/login.html')" not in text
    assert "sessionStorage.getItem('token')" in text
