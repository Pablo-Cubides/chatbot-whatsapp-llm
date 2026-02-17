"""Phase 6G contracts for mypy policy hardening."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_mypy_global_config_is_stricter_and_not_blanket_ignore() -> None:
    mypy_ini = (ROOT / "mypy.ini").read_text(encoding="utf-8")

    assert "disallow_untyped_defs = true" in mypy_ini
    assert "disallow_incomplete_defs = true" in mypy_ini
    assert "warn_unused_ignores = true" in mypy_ini
    assert "ignore_missing_imports = false" in mypy_ini


def test_mypy_tests_not_globally_ignored() -> None:
    mypy_ini = (ROOT / "mypy.ini").read_text(encoding="utf-8")

    assert "[mypy-tests.*]" not in mypy_ini or "ignore_errors = true" not in mypy_ini


def test_mypy_has_targeted_third_party_overrides() -> None:
    mypy_ini = (ROOT / "mypy.ini").read_text(encoding="utf-8")

    assert "[mypy-apscheduler.*]" in mypy_ini
    assert "[mypy-dotenv.*]" in mypy_ini
    assert "[mypy-playwright.*]" in mypy_ini
    assert "[mypy-psutil]" in mypy_ini
