"""Phase 6H contracts for metrics router placement and app wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_metrics_router_exists_under_routers_namespace() -> None:
    metrics_router = ROOT / "src" / "routers" / "metrics.py"
    assert metrics_router.exists()

    text = metrics_router.read_text(encoding="utf-8")
    assert "@router.get(\"/metrics\")" in text
    assert "@router.get(\"/metrics/json\")" in text


def test_admin_panel_wires_metrics_from_routers_module() -> None:
    admin_panel = (ROOT / "admin_panel.py").read_text(encoding="utf-8")
    assert "from src.routers.metrics import router as metrics_router" in admin_panel
