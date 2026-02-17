"""Tests for extracted LM Studio admin router."""

from fastapi.testclient import TestClient


def test_lmstudio_models_requires_auth(client: TestClient) -> None:
    response = client.get("/api/lmstudio/models")
    assert response.status_code == 401


def test_lmstudio_local_models_shape(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get("/api/lmstudio/models/local-only", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert "lm_studio_running" in payload
