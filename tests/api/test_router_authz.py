"""Router-level integration tests for auth enforcement and route wiring."""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.api


def test_auth_router_login_and_me(client: TestClient, admin_headers: dict[str, str]) -> None:
    me_response = client.get("/api/auth/me", headers=admin_headers)
    assert me_response.status_code == 200
    assert me_response.json().get("username") == "admin"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/business/config"),
        ("GET", "/api/reasoner-model"),
        ("GET", "/api/current-model"),
        ("GET", "/chat"),
        ("GET", "/dashboard"),
    ],
)
def test_protected_routes_require_auth(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path)
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/chat", {"chat_id": "test", "message": "hola"}),
        ("/api/chat/compose", {"chat_id": "test", "objective": "demo"}),
    ],
)
def test_protected_chat_endpoints_require_auth(client: TestClient, path: str, payload: dict[str, str]) -> None:
    response = client.post(path, json=payload)
    assert response.status_code == 401


def test_business_reset_is_not_get(client: TestClient, admin_headers: dict[str, str]) -> None:
    get_response = client.get("/api/business/config/reset", headers=admin_headers)
    assert get_response.status_code == 405

    post_response = client.post("/api/business/config/reset", headers=admin_headers)
    assert post_response.status_code in {200, 500}


def test_modular_routers_are_mounted(client: TestClient, admin_headers: dict[str, str]) -> None:
    checks = [
        ("GET", "/models"),
        ("GET", "/api/alerts"),
        ("GET", "/api/campaigns"),
        ("GET", "/api/audit/stats"),
        ("GET", "/api/business/fields"),
        ("GET", "/api/ai-models/available-providers"),
        ("GET", "/api/chats"),
        ("GET", "/api/verify"),
        ("GET", "/api/system/check-processes"),
        ("GET", "/api/lmstudio/models"),
        ("GET", "/api/current-model"),
        ("GET", "/api/whatsapp/status"),
        ("POST", "/api/chat/compose"),
    ]

    for method, path in checks:
        if method == "GET":
            response = client.get(path, headers=admin_headers)
        else:
            response = client.request(method, path, headers=admin_headers)

        assert response.status_code != 404, f"Route not mounted: {path}"


def test_webhook_verify_requires_required_params(client: TestClient) -> None:
    response = client.get("/webhooks/whatsapp")
    assert response.status_code == 400


def test_webhook_receive_rejects_invalid_signature(client: TestClient) -> None:
    response = client.post("/webhooks/whatsapp", json={"entry": []})
    assert response.status_code == 403


def test_stop_all_requires_admin_auth(client: TestClient) -> None:
    response = client.post("/api/system/stop-all")
    assert response.status_code == 401


def test_chat_toggle_requires_admin_auth(client: TestClient) -> None:
    response = client.post("/api/settings/chat/toggle")
    assert response.status_code == 401


def test_ai_models_test_apis_requires_auth(client: TestClient, admin_headers: dict[str, str]) -> None:
    unauthorized = client.post("/api/test-apis")
    assert unauthorized.status_code == 401

    authorized = client.post("/api/test-apis", headers=admin_headers)
    assert authorized.status_code == 200
    assert authorized.json().get("success") is True


def test_operator_cannot_access_admin_only_routes(client: TestClient, operator_headers: dict[str, str]) -> None:
    response = client.post("/api/system/stop-all", headers=operator_headers)
    assert response.status_code == 403


def test_legacy_token_is_rejected_in_jwt_only_mode() -> None:
    from admin_panel import app

    client = TestClient(app)
    previous_enabled = os.environ.get("LEGACY_TOKEN_ENABLED")
    previous_token = os.environ.get("LEGACY_ADMIN_TOKEN")

    try:
        os.environ["LEGACY_TOKEN_ENABLED"] = "true"
        os.environ["LEGACY_ADMIN_TOKEN"] = "test_admin_token"

        response = client.get("/api/auth/me", headers={"Authorization": "Bearer test_admin_token"})
        assert response.status_code == 401
    finally:
        if previous_enabled is None:
            os.environ.pop("LEGACY_TOKEN_ENABLED", None)
        else:
            os.environ["LEGACY_TOKEN_ENABLED"] = previous_enabled

        if previous_token is None:
            os.environ.pop("LEGACY_ADMIN_TOKEN", None)
        else:
            os.environ["LEGACY_ADMIN_TOKEN"] = previous_token
