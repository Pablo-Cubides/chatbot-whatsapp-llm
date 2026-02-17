from fastapi.testclient import TestClient


def test_calendar_status_requires_auth(client: TestClient) -> None:
    response = client.get("/api/calendar/status")
    assert response.status_code == 401


def test_calendar_status_with_auth_shape(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get("/api/calendar/status", headers=admin_headers)
    assert response.status_code == 200

    payload = response.json()
    assert "is_ready" in payload
    assert "available_providers" in payload
