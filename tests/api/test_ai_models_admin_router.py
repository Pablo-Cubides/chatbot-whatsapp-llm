from fastapi.testclient import TestClient


def test_ai_models_config_requires_auth(client: TestClient) -> None:
    response = client.get("/api/ai-models/config")
    assert response.status_code == 401


def test_ai_models_available_providers_shape(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get("/api/ai-models/available-providers", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("providers"), list)
    assert any(provider.get("type") == "gemini" for provider in payload["providers"])
