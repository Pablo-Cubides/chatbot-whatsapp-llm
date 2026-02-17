"""Phase 5B auth security: refresh rotation + websocket scope checks."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.services.auth_system import auth_manager

pytestmark = [pytest.mark.api, pytest.mark.security]


def _login(client: TestClient) -> dict:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": os.environ.get("ADMIN_PASSWORD", "test_admin_password")},
    )
    assert response.status_code == 200
    return response.json()


def test_refresh_token_rotation_rejects_reuse(client: TestClient) -> None:
    _login(client)
    first_refresh_cookie = client.cookies.get(auth_manager.refresh_cookie_name)
    assert first_refresh_cookie

    refresh_ok = client.post("/api/auth/refresh")
    assert refresh_ok.status_code == 200
    second_refresh_cookie = client.cookies.get(auth_manager.refresh_cookie_name)
    assert second_refresh_cookie and second_refresh_cookie != first_refresh_cookie

    client.cookies.set(auth_manager.refresh_cookie_name, first_refresh_cookie)
    replay = client.post("/api/auth/refresh")
    assert replay.status_code == 401


def test_logout_invalidates_refresh_session(client: TestClient) -> None:
    login_payload = _login(client)
    access_token = login_payload["access_token"]
    refresh_cookie = client.cookies.get(auth_manager.refresh_cookie_name)
    assert refresh_cookie

    headers = {"Authorization": f"Bearer {access_token}"}
    logout = client.post("/api/auth/logout", headers=headers)
    assert logout.status_code == 200

    client.cookies.set(auth_manager.refresh_cookie_name, refresh_cookie)
    refresh_after_logout = client.post("/api/auth/refresh")
    assert refresh_after_logout.status_code == 401


def test_ws_metrics_rejects_wrong_ws_scope_token(client: TestClient) -> None:
    login_payload = _login(client)
    access_token = login_payload["access_token"]
    access_payload = auth_manager.verify_token(access_token, expected_type="access")
    assert access_payload is not None

    ws_token_wrong_scope = auth_manager.create_ws_token(
        {
            "username": access_payload["sub"],
            "role": access_payload.get("role", "admin"),
            "permissions": access_payload.get("permissions", []),
        },
        scope="admin-panel",
        session_id=access_payload.get("sid"),
    )

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/metrics?token={ws_token_wrong_scope}"):
            pass

    assert exc_info.value.code == 1008
