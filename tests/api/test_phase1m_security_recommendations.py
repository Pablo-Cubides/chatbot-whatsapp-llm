"""Phase 1M security recommendations endpoint tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.services.audit_system import log_security_event

pytestmark = [pytest.mark.api, pytest.mark.security]


def test_security_recommendations_requires_admin(client: TestClient, operator_headers: dict[str, str]) -> None:
    unauthorized = client.get("/api/audit/security-recommendations")
    assert unauthorized.status_code == 401

    forbidden = client.get("/api/audit/security-recommendations", headers=operator_headers)
    assert forbidden.status_code == 403


def test_security_recommendations_return_baseline_when_healthy(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get(
        "/api/audit/security-recommendations",
        params={"window_minutes": 5},
        headers=admin_headers,
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload.get("recommendations")
    assert any(item.get("id") == "baseline-monitoring" for item in payload.get("recommendations", []))


def test_security_recommendations_include_targeted_actions_on_anomalies(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    for _ in range(5):
        log_security_event("login_failed", username="admin", role="admin", success=False, details={"reason": "bad-credentials"})
    for _ in range(8):
        log_security_event("refresh_failed", username="admin", role="admin", success=False, details={"reason": "missing_cookie"})

    response = client.get(
        "/api/audit/security-recommendations",
        params={"window_minutes": 120},
        headers=admin_headers,
    )
    assert response.status_code == 200

    payload = response.json()
    recommendations = payload.get("recommendations", [])
    ids = {item.get("id") for item in recommendations}
    assert "login-failed-spike" in ids
    assert "refresh-failed-spike" in ids
