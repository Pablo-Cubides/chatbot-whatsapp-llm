"""Integration flow: auth + business configuration endpoints."""

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_admin_can_read_preview_and_fields(client: TestClient, admin_headers: dict[str, str]) -> None:
    fields_resp = client.get("/api/business/fields", headers=admin_headers)
    assert fields_resp.status_code == 200
    fields_payload = fields_resp.json()
    assert isinstance(fields_payload, dict)

    preview_resp = client.get("/api/business/preview", headers=admin_headers)
    assert preview_resp.status_code == 200
    preview_payload = preview_resp.json()
    assert "generated_prompt" in preview_payload


def test_admin_updates_single_business_field(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/business/config/field",
        headers=admin_headers,
        json={"field": "business_info.name", "value": "Negocio Integración"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True

    get_resp = client.get("/api/business/config", headers=admin_headers)
    assert get_resp.status_code == 200
    assert "business_info" in get_resp.json()
