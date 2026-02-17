"""Phase 6N contracts for deploy compose preflight validation."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_ci_deploy_runs_compose_preflight_for_base_and_overlays() -> None:
    text = _read(".github/workflows/ci.yml")

    assert "Preflight: validate compose files before pull/up" in text
    assert "docker compose config -q" in text
    assert "docker compose -f docker-compose.yml -f docker-compose.proxy.yml config -q" in text
    assert "docker compose -f docker-compose.yml -f docker-compose.backup.yml config -q" in text


def test_deployment_docs_include_compose_preflight_commands() -> None:
    text = _read("docs/DEPLOYMENT.md")

    assert "Validar configuración compose antes de levantar servicios" in text
    assert "docker compose config -q" in text
    assert "docker compose -f docker-compose.yml -f docker-compose.proxy.yml config -q" in text
    assert "docker compose -f docker-compose.yml -f docker-compose.backup.yml config -q" in text
