"""Tests for extracted system admin router."""

from fastapi.testclient import TestClient


def test_system_check_processes_requires_auth(client: TestClient) -> None:
    response = client.get("/api/system/check-processes")
    assert response.status_code == 401


def test_system_check_processes_shape(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get("/api/system/check-processes", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert "success" in payload
    assert "ports_status" in payload
