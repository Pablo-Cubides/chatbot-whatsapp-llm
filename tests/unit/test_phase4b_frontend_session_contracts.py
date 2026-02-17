"""Phase 4B contracts for frontend session lifecycle and login accessibility flows."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_auth_logout_contract_keeps_cookie_based_logout_call() -> None:
    text = _read("ui/auth.js")

    assert "await rawFetch('/api/auth/logout'" in text
    assert "method: 'POST'" in text
    assert "credentials: 'include'" in text
    assert "headers: token ? { Authorization: `Bearer ${token}` } : {}" in text


def test_auth_clear_session_contract_clears_remember_and_idle_state() -> None:
    text = _read("ui/auth.js")

    assert "sessionStorage.removeItem('remember')" in text
    assert "sessionStorage.removeItem(LAST_ACTIVITY_KEY)" in text


def test_auth_session_guard_contract_tracks_activity_and_idle_checks() -> None:
    text = _read("ui/auth.js")

    assert "const events = ['click', 'keydown', 'mousemove', 'touchstart', 'scroll']" in text
    assert "window.setInterval(() => {" in text
    assert "}, 15000);" in text
    assert "auth.startSessionGuard('/ui/login.html')" in text


def test_login_page_contract_verifies_existing_token_and_handles_busy_state() -> None:
    text = _read("ui/login.html")

    assert "window.Auth.fetchWithAuth('/api/verify')" in text
    assert "document.getElementById('loginForm').setAttribute('aria-busy', 'true')" in text
    assert "document.getElementById('loginForm').setAttribute('aria-busy', 'false')" in text


def test_login_accessibility_modal_contract_keeps_focus_and_escape_flow() -> None:
    text = _read("ui/login.html")

    assert "modal.setAttribute('aria-hidden', 'false')" in text
    assert "modal.setAttribute('aria-hidden', 'true')" in text
    assert "if (event.key === 'Escape'" in text
    assert "closeBtn.focus()" in text
