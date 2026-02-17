"""Integration tests for end-to-end auth -> chat -> settings flow."""

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_auth_chat_settings_e2e(client: TestClient, admin_headers: dict[str, str]) -> None:
    me_response = client.get("/api/auth/me", headers=admin_headers)
    assert me_response.status_code == 200
    assert me_response.json().get("username") == "admin"

    compose_response = client.post(
        "/api/chat/compose",
        json={"chat_id": "integration-chat", "objective": "confirmar cita"},
        headers=admin_headers,
    )
    assert compose_response.status_code == 200
    compose_payload = compose_response.json()
    assert "success" in compose_payload

    update_settings_response = client.put(
        "/api/settings",
        json={"temperature": 0.6, "respond_to_all": False},
        headers=admin_headers,
    )
    assert update_settings_response.status_code == 200
    assert update_settings_response.json().get("ok") is True

    get_settings_response = client.get("/api/settings", headers=admin_headers)
    assert get_settings_response.status_code == 200
    settings_payload = get_settings_response.json()
    assert settings_payload.get("temperature") == 0.6
    assert settings_payload.get("respond_to_all") is False
