"""Phase 1F security telemetry/audit hardening tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.services.audit_system import audit_manager, log_security_event

pytestmark = [pytest.mark.api, pytest.mark.security]


def test_failed_login_emits_security_audit_event(client: TestClient, admin_headers: dict[str, str]) -> None:
    failed = client.post("/api/auth/login", json={"username": "admin", "password": "wrong-pass"})
    assert failed.status_code == 401

    logs_response = client.get("/api/audit/logs", params={"action": "SECURITY_LOGIN_FAILED"}, headers=admin_headers)
    assert logs_response.status_code == 200

    logs = logs_response.json().get("logs", [])
    assert logs, "Expected at least one SECURITY_LOGIN_FAILED event"
    assert any((entry.get("details") or {}).get("reason") == "invalid_credentials" for entry in logs)


def test_refresh_without_cookie_emits_security_event(client: TestClient, admin_headers: dict[str, str]) -> None:
    client.cookies.clear()
    response = client.post("/api/auth/refresh")
    assert response.status_code == 401

    logs_response = client.get("/api/audit/logs", params={"action": "SECURITY_REFRESH_FAILED"}, headers=admin_headers)
    assert logs_response.status_code == 200
    logs = logs_response.json().get("logs", [])
    assert logs
    assert any((entry.get("details") or {}).get("reason") == "missing_refresh_cookie" for entry in logs)


def test_unauthorized_websocket_emits_security_event(client: TestClient, admin_headers: dict[str, str]) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/metrics") as websocket:
            websocket.send_json({"type": "auth", "token": "invalid-token"})
            websocket.receive_json()

    assert exc_info.value.code == 1008

    logs_response = client.get("/api/audit/logs", params={"action": "SECURITY_WS_UNAUTHORIZED"}, headers=admin_headers)
    assert logs_response.status_code == 200
    logs = logs_response.json().get("logs", [])
    assert logs
    assert any((entry.get("details") or {}).get("reason") == "invalid_or_missing_ws_token" for entry in logs)


def test_security_event_details_are_redacted() -> None:
    log_security_event(
        "manual_redaction_test",
        username="admin",
        role="admin",
        success=False,
        details={"password": "secret", "nested": {"refresh_token": "abc", "ok": "yes"}},
    )

    logs = audit_manager.get_logs(action="SECURITY_MANUAL_REDACTION_TEST", limit=1)
    assert logs
    details = logs[0].get("details") or {}
    assert details.get("password") == "[REDACTED]"
    assert (details.get("nested") or {}).get("refresh_token") == "[REDACTED]"
    assert (details.get("nested") or {}).get("ok") == "yes"
