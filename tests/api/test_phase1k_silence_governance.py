"""Phase 1K silence governance tests (role policy limits)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.services.audit_system import log_security_event

pytestmark = [pytest.mark.api, pytest.mark.security]


def _create_security_alert(client: TestClient, admin_headers: dict[str, str]) -> str:
    log_security_event("refresh_failed", username="admin", role="admin", success=False, details={"reason": "test"})
    response = client.get(
        "/api/audit/security-anomalies",
        params={
            "window_minutes": 60,
            "refresh_failed_threshold": 1,
            "auto_create_alert": "true",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200
    alert_id = (response.json().get("security_alert") or {}).get("alert_id")
    assert alert_id
    return alert_id


def test_acknowledge_rejects_silence_above_role_policy(client: TestClient, admin_headers: dict[str, str]) -> None:
    alert_id = _create_security_alert(client, admin_headers)

    response = client.put(
        f"/api/alerts/{alert_id}/acknowledge-security",
        params={"silence_minutes": 9999, "reason": "too long"},
        headers=admin_headers,
    )
    assert response.status_code == 403


def test_renew_rejects_minutes_above_role_policy(client: TestClient, admin_headers: dict[str, str]) -> None:
    alert_id = _create_security_alert(client, admin_headers)
    ack = client.put(
        f"/api/alerts/{alert_id}/acknowledge-security",
        params={"silence_minutes": 30, "reason": "maintenance"},
        headers=admin_headers,
    )
    assert ack.status_code == 200
    fingerprint = ack.json().get("fingerprint")

    renew = client.post(
        "/api/audit/security-silences/renew",
        params={"fingerprint": fingerprint, "minutes": 9999},
        headers=admin_headers,
    )
    assert renew.status_code == 403


def test_silence_status_exposes_policy(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get("/api/audit/security-silences", headers=admin_headers)
    assert response.status_code == 200

    policy = (response.json() or {}).get("policy") or {}
    assert int(policy.get("max_silence_minutes", 0)) >= 1
