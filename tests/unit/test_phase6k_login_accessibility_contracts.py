"""Phase 6K contracts for login accessibility hardening."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_login_page_error_region_is_screen_reader_friendly() -> None:
    text = _read("ui/login.html")

    assert 'id="errorMessage"' in text
    assert 'role="alert"' in text
    assert 'aria-live="assertive"' in text
    assert 'aria-atomic="true"' in text
    assert 'tabindex="-1"' in text


def test_login_page_uses_autocomplete_and_modal_description_contracts() -> None:
    text = _read("ui/login.html")

    assert 'autocomplete="username"' in text
    assert 'autocomplete="current-password"' in text
    assert 'aria-describedby="contactAdminDescription"' in text
    assert 'id="contactAdminDescription"' in text


def test_login_runtime_marks_invalid_fields_and_focuses_error() -> None:
    text = _read("ui/login.js")

    assert "usernameInput.setAttribute('aria-invalid', 'false')" in text
    assert "passwordInput.setAttribute('aria-invalid', 'false')" in text
    assert "usernameInput.setAttribute('aria-invalid', 'true')" in text
    assert "passwordInput.setAttribute('aria-invalid', 'true')" in text
    assert "errorMessage.focus();" in text
