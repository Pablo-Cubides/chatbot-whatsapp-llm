"""Phase 4C contracts for protected UI route guards and API wrapper behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_setup_page_requires_auth_before_loading_existing_config() -> None:
    text = _read("ui/setup.html")

    assert "if (!window.Auth || !window.Auth.requireAuth('/ui/login.html'))" in text
    assert "loadExistingConfig();" in text


def test_main_dashboard_requires_auth_and_redirects_to_login() -> None:
    text = _read("ui/index.html")

    assert "if (!window.Auth || !window.Auth.requireAuth('/ui/login.html'))" in text
    assert "document.addEventListener('DOMContentLoaded', async function ()" in text


def test_dashboard_logout_prefers_auth_logout_and_has_session_fallback() -> None:
    text = _read("ui/index.html")

    assert "if (window.Auth && typeof window.Auth.logout === 'function')" in text
    assert "window.Auth.logout('/ui/login.html');" in text
    assert "sessionStorage.removeItem('token')" in text
    assert "window.location.href = '/ui/login.html';" in text


def test_api_wrapper_prefers_auth_fetch_and_surfaces_detail_on_http_error() -> None:
    text = _read("ui/api.js")

    assert "if (window.Auth && typeof window.Auth.fetchWithAuth === 'function')" in text
    assert "const detail = data?.detail || data?.message || `HTTP ${response.status}`;" in text
    assert "throw new Error(detail);" in text


def test_auth_interceptor_only_targets_api_routes_and_keeps_non_api_fetches_raw() -> None:
    text = _read("ui/auth.js")

    assert "if (!url.startsWith('/api/')) return false;" in text
    assert "return rawFetch(input, init);" in text
    assert "window.__authApiInterceptorInstalled" in text
