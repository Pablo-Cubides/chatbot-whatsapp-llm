"""Phase 5B deep security tests (lockout lifecycle, replay telemetry, websocket scope telemetry)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import src.services.auth_system as auth_module
from src.services.auth_system import auth_manager

pytestmark = [pytest.mark.api, pytest.mark.security]



def test_account_lockout_expires_and_allows_valid_login(create_user, monkeypatch: pytest.MonkeyPatch) -> None:
    create_user("phase5_lock_user", "StrongPass123", role="operator")

    now = [1_700_000_000.0]
    monkeypatch.setattr(auth_module.time, "time", lambda: now[0])

    last_error = None
    for _ in range(auth_manager.max_failed_login_attempts):
        _result, error_code, _seconds = auth_manager.authenticate_user_detailed("phase5_lock_user", "wrong-password")
        last_error = error_code

    assert last_error == "account_locked"

    now[0] += (auth_manager.account_lockout_minutes * 60) + 5
    success, error_code, _seconds = auth_manager.authenticate_user_detailed("phase5_lock_user", "StrongPass123")

    assert success is not None
    assert error_code is None



def test_refresh_replay_emits_invalid_refresh_security_event(client: TestClient, auth_headers_factory: callable) -> None:
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": os.environ.get("ADMIN_PASSWORD", "test_admin_password")},
    )
    assert login.status_code == 200

    old_refresh = client.cookies.get(auth_manager.refresh_cookie_name)
    assert old_refresh

    refresh_ok = client.post("/api/auth/refresh")
    assert refresh_ok.status_code == 200

    client.cookies.set(auth_manager.refresh_cookie_name, old_refresh)
    replay = client.post("/api/auth/refresh")
    assert replay.status_code == 401

    fresh_admin_headers = auth_headers_factory("admin", os.environ.get("ADMIN_PASSWORD", "test_admin_password"))
    logs_response = client.get(
        "/api/audit/logs",
        params={"action": "SECURITY_REFRESH_FAILED"},
        headers=fresh_admin_headers,
    )
    assert logs_response.status_code == 200

    logs = logs_response.json().get("logs", [])
    assert logs
    assert any((entry.get("details") or {}).get("reason") == "invalid_refresh_token" for entry in logs)



def test_ws_invalid_scope_emits_security_telemetry(client: TestClient, admin_headers: dict[str, str]) -> None:
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": os.environ.get("ADMIN_PASSWORD", "test_admin_password")},
    )
    assert login.status_code == 200
    access_token = login.json()["access_token"]

    payload = auth_manager.verify_token(access_token, expected_type="access")
    assert payload is not None

    wrong_scope_token = auth_manager.create_ws_token(
        {
            "username": payload["sub"],
            "role": payload.get("role", "admin"),
            "permissions": payload.get("permissions", []),
        },
        scope="admin-only",
        session_id=payload.get("sid"),
    )

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/metrics") as websocket:
            websocket.send_json({"type": "auth", "token": wrong_scope_token})
            websocket.receive_json()

    assert exc_info.value.code == 1008

    logs_response = client.get("/api/audit/logs", params={"action": "SECURITY_WS_INVALID_SCOPE"}, headers=admin_headers)
    assert logs_response.status_code == 200
    logs = logs_response.json().get("logs", [])
    assert logs
    assert any((entry.get("details") or {}).get("scope") == "admin-only" for entry in logs)
