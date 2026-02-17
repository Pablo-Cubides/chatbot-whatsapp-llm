"""Phase 1O incident snapshot handoff tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.services.audit_system import log_security_event

pytestmark = [pytest.mark.api, pytest.mark.security]


def test_security_incident_snapshot_requires_admin(client: TestClient, operator_headers: dict[str, str]) -> None:
    unauthorized = client.get("/api/audit/security-incident-snapshot")
    assert unauthorized.status_code == 401

    forbidden = client.get("/api/audit/security-incident-snapshot", headers=operator_headers)
    assert forbidden.status_code == 403


def test_security_incident_snapshot_returns_compact_handoff_payload(client: TestClient, admin_headers: dict[str, str]) -> None:
    for _ in range(5):
        log_security_event("login_failed", username="admin", role="admin", success=False, details={"reason": "bad-pass"})

    response = client.get(
        "/api/audit/security-incident-snapshot",
        params={"window_minutes": 120, "recent_events_limit": 10},
        headers=admin_headers,
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload.get("status") in {"healthy", "incident"}
    assert "anomalies" in payload
    assert "silences" in payload
    assert "recommended_actions" in payload
    assert "playbooks" in payload
    assert "recent_security_actions" in payload

    recent = payload.get("recent_security_actions", [])
    if recent:
        assert set(recent[0].keys()) == {"timestamp", "action", "username", "success"}


def test_security_incident_snapshot_respects_recent_events_limit(client: TestClient, admin_headers: dict[str, str]) -> None:
    for i in range(10):
        log_security_event("refresh_failed", username=f"user{i}", role="operator", success=False, details={"n": i})

    response = client.get(
        "/api/audit/security-incident-snapshot",
        params={"recent_events_limit": 3},
        headers=admin_headers,
    )
    assert response.status_code == 200

    recent = response.json().get("recent_security_actions", [])
    assert len(recent) <= 3
