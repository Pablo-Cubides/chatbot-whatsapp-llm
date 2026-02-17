"""Phase 1L SOC security overview endpoint tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.services.audit_system import log_security_event

pytestmark = [pytest.mark.api, pytest.mark.security]


def _create_silenced_security_fingerprint(client: TestClient, admin_headers: dict[str, str]) -> str:
    log_security_event("refresh_failed", username="admin", role="admin", success=False, details={"reason": "overview-test"})
    created = client.get(
        "/api/audit/security-anomalies",
        params={
            "window_minutes": 60,
            "refresh_failed_threshold": 1,
            "auto_create_alert": "true",
        },
        headers=admin_headers,
    )
    assert created.status_code == 200
    alert_id = (created.json().get("security_alert") or {}).get("alert_id")
    assert alert_id

    ack = client.put(
        f"/api/alerts/{alert_id}/acknowledge-security",
        params={"silence_minutes": 30, "reason": "SOC acknowledged"},
        headers=admin_headers,
    )
    assert ack.status_code == 200
    fingerprint = ack.json().get("fingerprint")
    assert fingerprint
    return fingerprint


def test_security_overview_requires_admin(client: TestClient, operator_headers: dict[str, str]) -> None:
    unauthorized = client.get("/api/audit/security-overview")
    assert unauthorized.status_code == 401

    forbidden = client.get("/api/audit/security-overview", headers=operator_headers)
    assert forbidden.status_code == 403


def test_security_overview_returns_consolidated_sections(client: TestClient, admin_headers: dict[str, str]) -> None:
    fingerprint = _create_silenced_security_fingerprint(client, admin_headers)
    log_security_event("login_failed", username="admin", role="admin", success=False, details={"reason": "bad-credentials"})

    response = client.get(
        "/api/audit/security-overview",
        params={"window_minutes": 120, "events_limit": 20},
        headers=admin_headers,
    )
    assert response.status_code == 200

    payload = response.json()
    assert "anomalies" in payload
    assert "silences" in payload
    assert "recent_security_actions" in payload

    silences = (payload.get("silences") or {}).get("items") or []
    assert any(item.get("fingerprint") == fingerprint for item in silences)

    actions = (payload.get("recent_security_actions") or {}).get("items") or []
    assert any(str(item.get("action", "")).startswith("SECURITY_") for item in actions)


def test_security_overview_respects_events_limit(client: TestClient, admin_headers: dict[str, str]) -> None:
    for i in range(10):
        log_security_event("login_failed", username=f"user{i}", role="operator", success=False, details={"n": i})

    response = client.get(
        "/api/audit/security-overview",
        params={"events_limit": 3},
        headers=admin_headers,
    )
    assert response.status_code == 200

    actions = (response.json().get("recent_security_actions") or {}).get("items") or []
    assert len(actions) <= 3
