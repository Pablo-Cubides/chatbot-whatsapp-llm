"""Phase 6U contracts for manual remote post-deploy verification workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_post_deploy_verification_workflow_exists_and_is_manual() -> None:
    text = _read(".github/workflows/post_deploy_verify.yml")

    assert "name: Post Deploy Verification" in text
    assert "workflow_dispatch:" in text
    assert "uses: appleboy/ssh-action@v1.0.3" in text
    assert "if: secrets.DEPLOY_HOST != '' && secrets.DEPLOY_USER != '' && secrets.DEPLOY_SSH_KEY != ''" in text


def test_post_deploy_verification_workflow_checks_health_metrics_auth_and_services() -> None:
    text = _read(".github/workflows/post_deploy_verify.yml")

    assert 'curl -fsS "${BASE_URL}/healthz"' in text
    assert 'curl -fsS "${BASE_URL}/metrics" | head -n 20' in text
    assert 'curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/auth/me"' in text
    assert 'curl -fsS -X POST "${BASE_URL}/api/auth/login"' in text
    assert 'curl -fsS "${BASE_URL}/api/auth/me" -H "Authorization: Bearer ${ACCESS_TOKEN}"' in text
    assert "for svc in app worker-web scheduler; do" in text
    assert "grep -Eiq \"Up|running|healthy\"" in text
