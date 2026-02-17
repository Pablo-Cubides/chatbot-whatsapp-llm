"""Phase 6J contracts for authenticated deploy smoke checks in CI workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_ci_deploy_smoke_checks_validate_auth_flow() -> None:
    text = _read(".github/workflows/ci.yml")

    assert "Expected /api/auth/me to return 401 without token" in text
    assert 'curl -fsS -X POST "http://localhost:8003/api/auth/login"' in text
    assert "Content-Type: application/json" in text
    assert "python3 -c \"import json,sys; print(json.load(sys.stdin).get('access_token',''))\"" in text
    assert 'Authorization: Bearer ${ACCESS_TOKEN}' in text
    assert "grep -q" in text
    assert '"username":"admin"' in text
