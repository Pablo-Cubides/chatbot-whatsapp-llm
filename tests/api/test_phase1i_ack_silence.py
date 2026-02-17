"""Phase 1I acknowledge/silence workflow tests for auto security alerts."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.services.audit_system import log_security_event

pytestmark = [pytest.mark.api, pytest.mark.security]


def _create_security_alert(client: TestClient, admin_headers: dict[str, str], event_name: str, threshold_param: str) -> str:
    log_security_event(event_name, username="admin", role="admin", success=False, details={"reason": "test"})
    response = client.get(
        "/api/audit/security-anomalies",
        params={
            "window_minutes": 60,
            threshold_param: 1,
            "auto_create_alert": "true",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    security_alert = payload.get("security_alert", {})
    assert security_alert.get("created") is True
    return security_alert["alert_id"]


def test_acknowledge_security_alert_requires_admin(client: TestClient, operator_headers: dict[str, str]) -> None:
    unauthorized = client.put("/api/alerts/fake-id/acknowledge-security")
    assert unauthorized.status_code == 401

    forbidden = client.put("/api/alerts/fake-id/acknowledge-security", headers=operator_headers)
    assert forbidden.status_code == 403


def test_acknowledge_security_alert_records_traceability(client: TestClient, admin_headers: dict[str, str]) -> None:
    alert_id = _create_security_alert(client, admin_headers, "login_failed", "login_failed_threshold")

    ack_response = client.put(
        f"/api/alerts/{alert_id}/acknowledge-security",
        params={"silence_minutes": 45, "reason": "Investigating incident"},
        headers=admin_headers,
    )
    assert ack_response.status_code == 200
    ack_payload = ack_response.json()
    assert ack_payload.get("success") is True
    assert ack_payload.get("silenced") is True

    logs_response = client.get(
        "/api/audit/logs",
        params={"action": "SECURITY_SECURITY_ALERT_ACKNOWLEDGED"},
        headers=admin_headers,
    )
    assert logs_response.status_code == 200
    logs = logs_response.json().get("logs", [])
    assert logs
    assert any((entry.get("details") or {}).get("alert_id") == alert_id for entry in logs)


def test_silenced_fingerprint_prevents_duplicate_auto_alert(client: TestClient, admin_headers: dict[str, str]) -> None:
    alert_id = _create_security_alert(client, admin_headers, "refresh_failed", "refresh_failed_threshold")

    ack_response = client.put(
        f"/api/alerts/{alert_id}/acknowledge-security",
        params={"silence_minutes": 60, "reason": "False positive while maintenance"},
        headers=admin_headers,
    )
    assert ack_response.status_code == 200

    log_security_event("refresh_failed", username="admin", role="admin", success=False, details={"reason": "test"})
    replay = client.get(
        "/api/audit/security-anomalies",
        params={
            "window_minutes": 60,
            "refresh_failed_threshold": 1,
            "auto_create_alert": "true",
        },
        headers=admin_headers,
    )
    assert replay.status_code == 200
    security_alert = (replay.json() or {}).get("security_alert", {})
    assert security_alert.get("created") is False
    assert security_alert.get("reason") == "silenced"
