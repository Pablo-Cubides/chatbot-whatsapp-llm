"""Phase 6R contracts for deploy failure diagnostics in CI/CD."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_ci_deploy_has_failure_trap_with_compose_diagnostics() -> None:
    text = _read(".github/workflows/ci.yml")

    assert "dump_diagnostics()" in text
    assert "docker compose ps || true" in text
    assert "docker compose logs --tail=120 app worker-web scheduler || true" in text
    assert "trap 'echo \"Deploy step failed; collecting diagnostics\"; dump_diagnostics' ERR" in text


def test_docs_include_quick_diagnostics_commands_for_failed_smokes() -> None:
    text = _read("docs/DEPLOYMENT.md")

    assert "Si algún smoke check falla, levantar diagnóstico rápido" in text
    assert "docker compose ps" in text
    assert "docker compose logs --tail=120 app worker-web scheduler" in text
