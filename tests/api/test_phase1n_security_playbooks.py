"""Phase 1N operational playbooks endpoint tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.services.audit_system import log_security_event

pytestmark = [pytest.mark.api, pytest.mark.security]


def test_security_playbooks_requires_admin(client: TestClient, operator_headers: dict[str, str]) -> None:
    unauthorized = client.get("/api/audit/security-playbooks")
    assert unauthorized.status_code == 401

    forbidden = client.get("/api/audit/security-playbooks", headers=operator_headers)
    assert forbidden.status_code == 403


def test_security_playbooks_return_baseline_when_healthy(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get("/api/audit/security-playbooks", params={"window_minutes": 5}, headers=admin_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload.get("playbooks")
    assert any(item.get("id") == "security-baseline-readiness" for item in payload.get("playbooks", []))


def test_security_playbooks_include_credential_abuse_playbook_on_login_anomalies(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    for _ in range(5):
        log_security_event("login_failed", username="admin", role="admin", success=False, details={"reason": "bad-pass"})

    response = client.get("/api/audit/security-playbooks", params={"window_minutes": 60}, headers=admin_headers)
    assert response.status_code == 200

    playbooks = response.json().get("playbooks", [])
    credential_playbook = next((item for item in playbooks if item.get("id") == "credential-abuse-response"), None)
    assert credential_playbook is not None
    assert credential_playbook.get("severity") == "high"
    assert len(credential_playbook.get("checklist", [])) >= 3
