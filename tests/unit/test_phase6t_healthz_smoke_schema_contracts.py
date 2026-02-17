"""Phase 6T contracts for healthz smoke schema validation in deploy workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_ci_deploy_validates_healthz_schema_and_required_components() -> None:
    text = _read(".github/workflows/ci.yml")

    assert 'HEALTH_JSON=$(curl -fsS "http://localhost:8003/healthz")' in text
    assert "healthz missing status" in text
    assert "healthz components invalid" in text
    assert "healthz missing components" in text
    assert "{'database','redis','disk','memory'}" in text


def test_deployment_docs_include_healthz_json_component_validation() -> None:
    text = _read("docs/DEPLOYMENT.md")

    assert "HEALTH_JSON=$(curl -fsS https://tu-dominio.com/healthz)" in text
    assert "python3 -c" in text
    assert "{'database','redis','disk','memory'}" in text
    assert "missing components" in text
