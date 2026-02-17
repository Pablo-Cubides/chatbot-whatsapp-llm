"""Phase 1A auth/authz hardening tests."""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.api, pytest.mark.security]


def _login(client: TestClient, username: str, password: str):
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )


def test_login_rate_limit_5_per_5_minutes(client: TestClient) -> None:
    for _ in range(5):
        response = _login(client, "nonexistent-user", "wrong-password")
        assert response.status_code == 401

    blocked = _login(client, "nonexistent-user", "wrong-password")
    assert blocked.status_code == 429


def test_logout_revokes_current_token(client: TestClient) -> None:
    login_response = _login(client, "admin", os.environ.get("ADMIN_PASSWORD", "test_admin_password"))
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    me_before = client.get("/api/auth/me", headers=headers)
    assert me_before.status_code == 200

    logout_response = client.post("/api/auth/logout", headers=headers)
    assert logout_response.status_code == 200

    me_after = client.get("/api/auth/me", headers=headers)
    assert me_after.status_code == 401


def test_refresh_endpoint_issues_new_access_token(client: TestClient) -> None:
    login_response = _login(client, "admin", os.environ.get("ADMIN_PASSWORD", "test_admin_password"))
    assert login_response.status_code == 200

    refresh_response = client.post("/api/auth/refresh")
    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload.get("access_token")

    headers = {"Authorization": f"Bearer {refresh_payload['access_token']}"}
    me_response = client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200


def test_account_lockout_after_five_failed_attempts(client: TestClient, create_user) -> None:
    create_user("locked_user", "ValidPass123", role="operator")

    for i in range(5):
        response = _login(client, "locked_user", f"wrong-{i}")
        if i < 4:
            assert response.status_code == 401
        else:
            assert response.status_code == 423


def test_operator_cannot_access_settings_and_prompts(client: TestClient, operator_headers: dict[str, str]) -> None:
    checks = [
        ("GET", "/api/settings", None),
        ("PUT", "/api/settings", {"temperature": 0.5}),
        ("GET", "/api/prompts", None),
        ("PUT", "/api/prompts", {"conversational": "test"}),
    ]

    for method, path, payload in checks:
        if method == "GET":
            response = client.get(path, headers=operator_headers)
        else:
            response = client.put(path, json=payload, headers=operator_headers)
        assert response.status_code == 403
