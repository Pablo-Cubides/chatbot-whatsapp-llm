"""Integration flow: custom user factory + auth + role-based access."""

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_create_user_factory_and_login(
    client: TestClient,
    create_user: callable,
    auth_headers_factory: callable,
) -> None:
    user = create_user("integration_operator", "OperatorPass123", role="operator", permissions=["view"])
    headers = auth_headers_factory(user["username"], user["password"])

    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    payload = me_resp.json()
    assert payload.get("sub") == "integration_operator"


def test_custom_operator_cannot_call_admin_endpoint(
    client: TestClient,
    create_user: callable,
    auth_headers_factory: callable,
) -> None:
    user = create_user("integration_operator2", "OperatorPass123", role="operator", permissions=["view"])
    headers = auth_headers_factory(user["username"], user["password"])

    response = client.post("/api/system/stop-all", headers=headers)
    assert response.status_code == 403
