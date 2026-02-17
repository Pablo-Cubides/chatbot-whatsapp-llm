"""Phase 1D websocket hardening tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.services.auth_system import auth_manager

pytestmark = [pytest.mark.api, pytest.mark.security]


def test_ws_token_requires_auth(client: TestClient) -> None:
    response = client.post("/api/auth/ws-token")
    assert response.status_code == 401


def test_ws_token_is_short_lived_and_scoped(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.post("/api/auth/ws-token", headers=admin_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload.get("scope") == "metrics"
    assert payload.get("ws_token")
    assert int(payload.get("expires_in", 0)) > 0

    ws_payload = auth_manager.verify_token(payload["ws_token"], expected_type="ws")
    assert ws_payload is not None
    assert ws_payload.get("ws_scope") == "metrics"


def test_ws_metrics_rejects_access_token(client: TestClient, admin_headers: dict[str, str]) -> None:
    access_token = admin_headers["Authorization"].split(" ", 1)[1]

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/metrics") as websocket:
            websocket.send_json({"type": "auth", "token": access_token})
            websocket.receive_json()

    assert exc_info.value.code == 1008


def test_ws_metrics_accepts_scoped_ws_token(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.post("/api/auth/ws-token", headers=admin_headers)
    assert response.status_code == 200
    ws_token = response.json()["ws_token"]

    with client.websocket_connect("/ws/metrics") as websocket:
        websocket.send_json({"type": "auth", "token": ws_token})
        message = websocket.receive_json()
        assert message.get("type") == "metrics"


def test_ws_metrics_rejects_query_token(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.post("/api/auth/ws-token", headers=admin_headers)
    assert response.status_code == 200
    ws_token = response.json()["ws_token"]

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/metrics?token={ws_token}"):
            pass

    assert exc_info.value.code == 1008
