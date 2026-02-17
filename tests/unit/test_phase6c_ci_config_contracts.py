"""Phase 6C contracts for CI/CD and build reproducibility configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_ci_workflow_has_coverage_gate_and_strict_mypy() -> None:
    text = _read(".github/workflows/ci.yml")

    assert "PYTHON_VERSION: \"3.11.8\"" in text
    assert "--cov-fail-under=70" in text
    assert "mypy --config-file mypy.ini --strict" in text


def test_precommit_has_fast_pytest_hook() -> None:
    text = _read(".pre-commit-config.yaml")

    assert "id: pytest-fast" in text
    assert "entry: pytest -q -m \"unit and not integration\"" in text


def test_dependabot_weekly_for_pip_and_docker() -> None:
    text = _read(".github/dependabot.yml")

    assert "package-ecosystem: \"pip\"" in text
    assert "package-ecosystem: \"docker\"" in text
    assert "interval: \"weekly\"" in text


def test_dockerfiles_pin_python_patch_version() -> None:
    dockerfile = _read("Dockerfile")
    scheduler = _read("Dockerfile.scheduler")

    assert "FROM python:3.11.8-slim AS builder" in dockerfile
    assert "FROM python:3.11.8-slim AS runtime" in dockerfile

    assert "FROM python:3.11.8-slim AS builder" in scheduler
    assert "FROM python:3.11.8-slim AS runtime" in scheduler
