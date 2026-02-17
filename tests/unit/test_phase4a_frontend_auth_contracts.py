"""Phase 4A contracts for frontend authentication and UI login hardening."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_login_flow_posts_to_auth_endpoint_with_cookie_credentials() -> None:
    text = _read("ui/login.html")

    assert "fetch('/api/auth/login'" in text
    assert "credentials: 'include'" in text
    assert "sessionStorage.setItem('token', data.access_token)" in text


def test_login_ui_keeps_accessibility_and_integrity_baseline() -> None:
    text = _read("ui/login.html")

    assert 'role="dialog"' in text
    assert 'aria-modal="true"' in text
    assert "integrity=" in text


def test_auth_runtime_has_refresh_and_idle_timeout_guards() -> None:
    text = _read("ui/auth.js")

    assert "DEFAULT_IDLE_TIMEOUT_MS" in text
    assert "REMEMBER_IDLE_TIMEOUT_MS" in text
    assert "async refreshAccessToken()" in text
    assert "if (response.status !== 401)" in text


def test_auth_fetch_interceptor_skips_login_and_refresh_routes() -> None:
    text = _read("ui/auth.js")

    assert "url.startsWith('/api/auth/login')" in text
    assert "url.startsWith('/api/auth/refresh')" in text
