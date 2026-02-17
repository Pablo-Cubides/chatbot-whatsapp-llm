"""Phase 5A campaign + business config integration-style API coverage."""

from __future__ import annotations

import copy
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.routers import campaigns as campaigns_router
from src.routers import deps
from src.routers import business_config as business_config_router

pytestmark = [pytest.mark.api]


@pytest.fixture
def restore_business_config() -> dict:
    snapshot = copy.deepcopy(business_config_router.business_config.config)
    try:
        yield snapshot
    finally:
        business_config_router.business_config.config = snapshot


def test_create_campaign_enqueues_bulk_messages_with_scheduling(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_rows: list[dict] = []

    def _create_campaign(name: str, created_by: str, total_messages: int, metadata: dict | None = None) -> str:
        assert name == "Campaña Fase 5"
        assert created_by
        assert total_messages == 3
        assert metadata
        return "camp_phase5"

    def _enqueue_bulk(rows: list[dict]) -> list[str]:
        captured_rows.extend(rows)
        return [f"msg-{idx}" for idx, _ in enumerate(rows, start=1)]

    monkeypatch.setattr(deps.queue_manager, "create_campaign", _create_campaign)
    monkeypatch.setattr(deps.queue_manager, "enqueue_bulk_messages", _enqueue_bulk)
    monkeypatch.setattr(campaigns_router.queue_manager, "create_campaign", _create_campaign)
    monkeypatch.setattr(campaigns_router.queue_manager, "enqueue_bulk_messages", _enqueue_bulk)

    response = client.post(
        "/api/campaigns",
        headers=admin_headers,
        json={
            "name": "Campaña Fase 5",
            "template": "Hola, recordatorio de cita",
            "contacts": ["573001112233", "573002224455", "573003336677"],
            "scheduled_at": "2030-01-01T10:00:00Z",
            "delay_between_messages": 30,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("success") is True
    assert payload.get("campaign_id") == "camp_phase5"

    assert len(captured_rows) == 3
    when_values = [row.get("when") for row in captured_rows]
    assert all(isinstance(item, datetime) for item in when_values)
    assert int((when_values[1] - when_values[0]).total_seconds()) == 30
    assert int((when_values[2] - when_values[1]).total_seconds()) == 30


def test_business_config_update_export_import_and_reset(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    restore_business_config,
) -> None:
    monkeypatch.setattr(business_config_router.business_config, "save_config", lambda *_args, **_kwargs: True)

    update_resp = client.post(
        "/api/business/config",
        headers=admin_headers,
        json={"business_info": {"name": "Negocio Fase 5"}},
    )
    assert update_resp.status_code == 200
    assert update_resp.json().get("success") is True

    get_resp = client.get("/api/business/config", headers=admin_headers)
    assert get_resp.status_code == 200
    assert "business_info" in get_resp.json()

    export_resp = client.post("/api/business/config/export", headers=admin_headers)
    assert export_resp.status_code == 200
    assert "application/json" in export_resp.headers.get("content-type", "")

    imported_config = {"business_info": {"name": "Importado Fase 5"}}

    def _import_config(config_json: str) -> bool:
        parsed = json.loads(config_json)
        business_config_router.business_config.config = business_config_router.business_config._merge_configs(
            business_config_router.business_config.get_default_config(),
            parsed,
        )
        return True

    monkeypatch.setattr(business_config_router.business_config, "import_config", _import_config)

    import_resp = client.post(
        "/api/business/config/import",
        headers=admin_headers,
        files={"file": ("config.json", json.dumps(imported_config).encode("utf-8"), "application/json")},
    )
    assert import_resp.status_code == 200
    assert import_resp.json().get("success") is True

    reset_resp = client.post("/api/business/config/reset", headers=admin_headers)
    assert reset_resp.status_code == 200
    assert reset_resp.json().get("success") is True
