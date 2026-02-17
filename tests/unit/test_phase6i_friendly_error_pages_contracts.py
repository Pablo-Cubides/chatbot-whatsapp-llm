"""Phase 6I contracts for friendly UI error pages."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    file_path = ROOT / path
    assert file_path.exists(), f"Missing file: {path}"
    return file_path.read_text(encoding="utf-8")


def test_ui_500_page_exists_and_links_dashboard() -> None:
    text = _read("ui/500.html")

    assert "<h1 class=\"error-code\">500</h1>" in text
    assert "href=\"/ui/index.html\"" in text
    assert "/ui/common.css" in text
    assert "/ui/500.css" in text


def test_admin_panel_uses_custom_500_for_non_api_routes() -> None:
    text = _read("admin_panel.py")

    assert 'request.url.path.startswith("/api")' in text
    assert 'custom_500 = os.path.join(os.path.dirname(__file__), "ui", "500.html")' in text
    assert 'return HTMLResponse(content=file_handler.read(), status_code=500)' in text
