"""Tests for extracted manual messaging admin router."""

from fastapi.testclient import TestClient


def test_chat_compose_requires_auth(client: TestClient) -> None:
    response = client.post("/api/chat/compose", json={"chat_id": "test", "objective": "demo"})
    assert response.status_code == 401


def test_chat_compose_shape_with_auth(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/chat/compose",
        headers=admin_headers,
        json={"chat_id": "test", "objective": "demo"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "success" in payload
