"""Phase 1C browser/header hardening tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.api, pytest.mark.security]


def test_api_uses_restrictive_csp(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "test_admin_password"})
    assert response.status_code == 200

    csp = response.headers.get("Content-Security-Policy", "")
    assert "default-src 'none'" in csp
    assert "form-action 'none'" in csp
    assert "'unsafe-inline'" not in csp


def test_api_responses_are_not_cacheable(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "test_admin_password"})
    assert response.status_code == 200
    assert "no-store" in response.headers.get("Cache-Control", "")
    assert response.headers.get("Pragma") == "no-cache"


def test_chat_ui_is_not_cacheable(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get("/chat", headers=admin_headers)
    assert response.status_code == 200
    assert "no-store" in response.headers.get("Cache-Control", "")
    assert response.headers.get("Pragma") == "no-cache"


def test_chat_template_no_longer_depends_on_external_cdn(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get("/chat", headers=admin_headers)
    assert response.status_code == 200
    assert "cdnjs.cloudflare.com" not in response.text
