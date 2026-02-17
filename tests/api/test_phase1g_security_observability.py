"""Phase 1G security observability tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.services.audit_system import log_security_event

pytestmark = [pytest.mark.api, pytest.mark.security]


def test_security_anomalies_endpoint_requires_admin(client: TestClient, operator_headers: dict[str, str]) -> None:
    unauthorized = client.get("/api/audit/security-anomalies")
    assert unauthorized.status_code == 401

    forbidden = client.get("/api/audit/security-anomalies", headers=operator_headers)
    assert forbidden.status_code == 403


def test_security_anomalies_detect_threshold_breach(client: TestClient, admin_headers: dict[str, str]) -> None:
    log_security_event(
        "login_failed",
        username="admin",
        role="admin",
        success=False,
        details={"reason": "invalid_credentials"},
    )

    response = client.get(
        "/api/audit/security-anomalies",
        params={"window_minutes": 60, "login_failed_threshold": 1},
        headers=admin_headers,
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload.get("healthy") is False
    anomalies = payload.get("anomalies", [])
    assert any(item.get("event") == "SECURITY_LOGIN_FAILED" for item in anomalies)


def test_security_anomalies_is_healthy_without_events(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get(
        "/api/audit/security-anomalies",
        params={"window_minutes": 5, "login_failed_threshold": 5},
        headers=admin_headers,
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload.get("healthy") is True
    assert payload.get("anomalies") == []
