"""Phase 1H automatic response tests for security anomalies."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.services.audit_system import log_security_event

pytestmark = [pytest.mark.api, pytest.mark.security]


def test_security_anomalies_can_create_operational_alert(client: TestClient, admin_headers: dict[str, str]) -> None:
    log_security_event("login_failed", username="admin", role="admin", success=False, details={"reason": "invalid_credentials"})

    response = client.get(
        "/api/audit/security-anomalies",
        params={
            "window_minutes": 60,
            "login_failed_threshold": 1,
            "auto_create_alert": "true",
            "alert_cooldown_minutes": 30,
        },
        headers=admin_headers,
    )
    assert response.status_code == 200

    payload = response.json()
    security_alert = payload.get("security_alert", {})
    assert security_alert.get("created") is True
    assert security_alert.get("alert_id")

    alerts_response = client.get(
        "/api/alerts",
        params={"chat_id": "security:platform"},
        headers=admin_headers,
    )
    assert alerts_response.status_code == 200
    assert alerts_response.json().get("count", 0) >= 1


def test_security_anomalies_auto_alert_respects_cooldown(client: TestClient, admin_headers: dict[str, str]) -> None:
    log_security_event("refresh_failed", username="admin", role="admin", success=False, details={"reason": "missing_refresh_cookie"})

    first = client.get(
        "/api/audit/security-anomalies",
        params={
            "window_minutes": 60,
            "refresh_failed_threshold": 1,
            "auto_create_alert": "true",
            "alert_cooldown_minutes": 60,
        },
        headers=admin_headers,
    )
    assert first.status_code == 200
    assert (first.json().get("security_alert") or {}).get("created") is True

    second = client.get(
        "/api/audit/security-anomalies",
        params={
            "window_minutes": 60,
            "refresh_failed_threshold": 1,
            "auto_create_alert": "true",
            "alert_cooldown_minutes": 60,
        },
        headers=admin_headers,
    )
    assert second.status_code == 200
    payload = second.json()
    security_alert = payload.get("security_alert", {})
    assert security_alert.get("created") is False
    assert security_alert.get("reason") == "cooldown"


def test_security_anomalies_auto_alert_skips_when_healthy(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get(
        "/api/audit/security-anomalies",
        params={
            "window_minutes": 5,
            "login_failed_threshold": 99,
            "auto_create_alert": "true",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200

    payload = response.json()
    security_alert = payload.get("security_alert", {})
    assert payload.get("healthy") is True
    assert security_alert.get("created") is False
    assert security_alert.get("reason") == "no_anomalies"
