"""Phase 4D contracts for protected dashboard pages and authenticated API call baselines."""

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
def test_protected_pages_load_auth_and_api_runtime(rel_path: str) -> None:
    text = _read(rel_path)

    assert '<script src="/ui/auth.js"></script>' in text
    assert '<script src="/ui/api.js"></script>' in text


@pytest.mark.parametrize(
    "rel_path",
    [
        "ui/analytics.html",
        "ui/alerts.html",
        "ui/business_config.html",
        "ui/calendar_config.html",
        "ui/chat.html",
        "ui/index.html",
        "ui/setup.html",
    ],
)
def test_pages_use_centralized_api_wrapper_and_avoid_legacy_token_pattern(rel_path: str) -> None:
    text = _read(rel_path)

    assert "window.Api" in text or "apiJson(" in text or "apiRequest(" in text
    assert "sessionStorage.getItem('token')" not in text
    assert "Authorization" not in text


@pytest.mark.parametrize("rel_path", PROTECTED_PAGES)
def test_protected_pages_include_explicit_auth_guard(rel_path: str) -> None:
    text = _read(rel_path)

    assert "requireAuth('/ui/login.html')" in text


def test_realtime_dashboard_uses_api_wrapper_for_ws_token_bootstrap() -> None:
    text = _read("ui/realtime_dashboard.html")

    assert "window.Api.json('/api/auth/ws-token'" in text
    assert "window.Auth.refreshAccessToken()" in text
    assert "ws.send(JSON.stringify({" in text
    assert "type: 'auth'" in text
