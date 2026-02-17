"""Phase 6V contracts for beta go-live checklist and deployment docs linkage."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_beta_go_live_checklist_exists_with_core_operational_sections() -> None:
    text = _read("docs/BETA_GO_LIVE_CHECKLIST.md")

    assert "# ✅ Beta Go-Live Checklist" in text
    assert "## 1) Secrets y credenciales" in text
    assert "## 2) Base de datos y migraciones" in text
    assert "## 3) Runtime y salud de servicios" in text
    assert "## 4) Seguridad operativa" in text
    assert "## 5) Monitoreo y respuesta a incidentes" in text
    assert "## 6) Rollback y continuidad" in text
    assert "## 7) Evidencia final de release" in text
    assert "RATE_LIMIT_ENABLED=true" in text


def test_deployment_docs_reference_manual_verification_and_go_live_checklist() -> None:
    text = _read("docs/DEPLOYMENT.md")

    assert "Verificación real en host remoto (manual)" in text
    assert "post_deploy_verify.yml" in text
    assert "Post Deploy Verification" in text
    assert "BETA_GO_LIVE_CHECKLIST.md" in text
