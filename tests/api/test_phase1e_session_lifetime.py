"""Phase 1E session lifetime hardening tests."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from src.services.auth_system import auth_manager

pytestmark = [pytest.mark.api, pytest.mark.security]


def test_refresh_rejects_sessions_older_than_max_lifetime(client: TestClient) -> None:
    stale_auth_time = int(time.time()) - (auth_manager.max_session_hours * 60 * 60) - 120
    stale_refresh = auth_manager.create_refresh_token(
        {
            "username": "admin",
            "role": "admin",
            "permissions": ["all"],
            "auth_time": stale_auth_time,
        },
        session_id="stale-session",
    )

    client.cookies.set(auth_manager.refresh_cookie_name, stale_refresh)
    response = client.post("/api/auth/refresh")
    assert response.status_code == 401


def test_refresh_accepts_session_within_max_lifetime(client: TestClient) -> None:
    fresh_auth_time = int(time.time()) - 60
    fresh_refresh = auth_manager.create_refresh_token(
        {
            "username": "admin",
            "role": "admin",
            "permissions": ["all"],
            "auth_time": fresh_auth_time,
        },
        session_id="fresh-session",
    )

    client.cookies.set(auth_manager.refresh_cookie_name, fresh_refresh)
    response = client.post("/api/auth/refresh")
    assert response.status_code == 200
    assert response.json().get("access_token")
