"""Tests for extracted chat/files admin router."""

from fastapi.testclient import TestClient


def test_chat_files_routes_require_auth(client: TestClient) -> None:
    response = client.get("/api/chats")
    assert response.status_code == 401


def test_chat_files_routes_are_mounted(client: TestClient, admin_headers: dict[str, str]) -> None:
    chats_response = client.get("/api/chats", headers=admin_headers)
    assert chats_response.status_code == 200
    assert "chats" in chats_response.json()

    files_response = client.get("/api/files/perfil", headers=admin_headers)
    assert files_response.status_code in {200, 500}
