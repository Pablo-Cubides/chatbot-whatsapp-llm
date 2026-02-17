"""Phase 6Q contracts for deploy runtime status smoke checks."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_ci_deploy_checks_critical_services_running_and_no_unhealthy() -> None:
    text = _read(".github/workflows/ci.yml")

    assert "Runtime status checks for critical services" in text
    assert "for svc in app worker-web scheduler; do" in text
    assert "Service $svc is not running/healthy" in text
    assert "grep -Eiq \"Up|running|healthy\"" in text
    assert "grep -Eiq \"unhealthy|Exited|dead\"" in text
    assert "Detected unhealthy/exited containers after deploy" in text


def test_deployment_docs_include_critical_service_runtime_check_commands() -> None:
    text = _read("docs/DEPLOYMENT.md")

    assert "Estado de servicios críticos" in text
    assert "docker compose ps" in text
    assert "for svc in app worker-web scheduler; do" in text
    assert "grep -Eiq \"Up|running|healthy\"" in text
