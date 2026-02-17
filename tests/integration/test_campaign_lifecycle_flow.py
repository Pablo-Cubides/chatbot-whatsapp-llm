"""Integration flow: create/pause/resume/cancel campaign."""

import pytest
from fastapi.testclient import TestClient

from src.routers import deps
from src.routers import campaigns as campaigns_router

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("contacts", [["573001112233"], ["573001112233", "573002224455"]])
def test_campaign_lifecycle(
    client: TestClient,
    admin_headers: dict[str, str],
    contacts: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaigns: dict[str, dict[str, object]] = {}

    def _create_campaign(name: str, created_by: str, total_messages: int, metadata: dict[str, object] | None = None) -> str:
        campaign_id = f"camp_test_{len(campaigns) + 1}"
        campaigns[campaign_id] = {
            "campaign_id": campaign_id,
            "name": name,
            "status": "active",
            "created_by": created_by,
            "created_at": "2026-01-01T00:00:00+00:00",
            "total_messages": total_messages,
            "sent_messages": 0,
            "failed_messages": 0,
            "metadata": metadata or {},
        }
        return campaign_id

    def _get_campaign_status(campaign_id: str) -> dict[str, object] | None:
        return campaigns.get(campaign_id)

    def _pause_campaign(campaign_id: str) -> bool:
        if campaign_id not in campaigns:
            return False
        campaigns[campaign_id]["status"] = "paused"
        return True

    def _resume_campaign(campaign_id: str) -> bool:
        if campaign_id not in campaigns:
            return False
        campaigns[campaign_id]["status"] = "active"
        return True

    def _cancel_campaign(campaign_id: str) -> bool:
        if campaign_id not in campaigns:
            return False
        campaigns[campaign_id]["status"] = "cancelled"
        return True

    monkeypatch.setattr(deps.queue_manager, "create_campaign", _create_campaign)
    monkeypatch.setattr(deps.queue_manager, "enqueue_message", lambda *args, **kwargs: "msg_test")
    monkeypatch.setattr(deps.queue_manager, "get_campaign_status", _get_campaign_status)
    monkeypatch.setattr(deps.queue_manager, "pause_campaign", _pause_campaign)
    monkeypatch.setattr(deps.queue_manager, "resume_campaign", _resume_campaign)
    monkeypatch.setattr(deps.queue_manager, "cancel_campaign", _cancel_campaign)
    monkeypatch.setattr(campaigns_router.queue_manager, "create_campaign", _create_campaign)
    monkeypatch.setattr(campaigns_router.queue_manager, "enqueue_message", lambda *args, **kwargs: "msg_test")
    monkeypatch.setattr(campaigns_router.queue_manager, "get_campaign_status", _get_campaign_status)
    monkeypatch.setattr(campaigns_router.queue_manager, "pause_campaign", _pause_campaign)
    monkeypatch.setattr(campaigns_router.queue_manager, "resume_campaign", _resume_campaign)
    monkeypatch.setattr(campaigns_router.queue_manager, "cancel_campaign", _cancel_campaign)

    create_resp = client.post(
        "/api/campaigns",
        headers=admin_headers,
        json={
            "name": "Campaña Integración",
            "template": "Hola {{name}}",
            "contacts": contacts,
            "delay_between_messages": 1,
        },
    )

    assert create_resp.status_code == 200, create_resp.text
    create_payload = create_resp.json()
    assert create_payload.get("success") is True
    campaign_id = create_payload.get("campaign_id")
    assert campaign_id

    status_resp = client.get(f"/api/campaigns/{campaign_id}", headers=admin_headers)
    assert status_resp.status_code == 200

    pause_resp = client.post(f"/api/campaigns/{campaign_id}/pause", headers=admin_headers)
    assert pause_resp.status_code == 200
    assert pause_resp.json().get("success") is True

    resume_resp = client.post(f"/api/campaigns/{campaign_id}/resume", headers=admin_headers)
    assert resume_resp.status_code == 200
    assert resume_resp.json().get("success") is True

    cancel_resp = client.post(f"/api/campaigns/{campaign_id}/cancel", headers=admin_headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json().get("success") is True
