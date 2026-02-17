"""Phase 5A coverage for manual messaging + WhatsApp runtime routers."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.routers import manual_messaging_admin as manual_router
from src.routers import whatsapp_runtime_admin as runtime_router



def test_whatsapp_send_requires_runtime_running(client: TestClient, admin_headers: dict[str, str], monkeypatch) -> None:
    monkeypatch.setattr(manual_router, "get_whatsapp_runtime_status", lambda: {"status": "stopped"})

    response = client.post(
        "/api/whatsapp/send",
        headers=admin_headers,
        json={"chat_id": "573001112233", "message": "hola"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is False
    assert "automator" in payload.get("error", "").lower()



def test_whatsapp_send_enqueues_message_and_history(client: TestClient, admin_headers: dict[str, str], monkeypatch) -> None:
    captured: dict[str, object] = {}
    saved_history: dict[str, object] = {}

    def _enqueue_message(**kwargs):
        captured.update(kwargs)
        return "msg_phase5"

    def _save_context(chat_id: str, history: list[dict[str, object]]) -> None:
        saved_history["chat_id"] = chat_id
        saved_history["history"] = history

    monkeypatch.setattr(manual_router, "get_whatsapp_runtime_status", lambda: {"status": "running"})
    monkeypatch.setattr(manual_router.queue_manager, "enqueue_message", _enqueue_message)
    monkeypatch.setattr(manual_router.chat_sessions, "load_last_context", lambda _chat_id: [])
    monkeypatch.setattr(manual_router.chat_sessions, "save_context", _save_context)

    response = client.post(
        "/api/whatsapp/send",
        headers=admin_headers,
        json={
            "chat_id": "573001112233",
            "message": "recordatorio de cita",
            "media": {"fileId": "file_1", "type": "image"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True

    assert captured.get("chat_id") == "573001112233"
    assert captured.get("message") == "recordatorio de cita"
    assert captured.get("priority") == 1
    assert isinstance(captured.get("metadata"), dict)
    assert captured["metadata"]["source"] == "manual_admin"
    assert captured["metadata"]["media"]["fileId"] == "file_1"

    assert saved_history.get("chat_id") == "573001112233"
    assert isinstance(saved_history.get("history"), list)
    assert saved_history["history"][-1]["manual"] is True



def test_bulk_send_campaign_creates_and_enqueues(client: TestClient, admin_headers: dict[str, str], monkeypatch) -> None:
    captured_bulk: list[dict[str, object]] = []

    monkeypatch.setattr(manual_router.queue_manager, "create_campaign", lambda **_kwargs: "camp_phase5_bulk")

    def _enqueue_message(**kwargs):
        captured_bulk.append(kwargs)
        return f"msg_{len(captured_bulk)}"

    monkeypatch.setattr(manual_router.queue_manager, "enqueue_message", _enqueue_message)
    monkeypatch.setattr(manual_router.stub_chat, "chat", lambda *_args, **_kwargs: "contenido personalizado")
    monkeypatch.setattr(manual_router.chat_sessions, "load_last_context", lambda _chat_id: [])
    monkeypatch.setattr(manual_router.chat_sessions, "save_context", lambda *_args, **_kwargs: None)

    response = client.post(
        "/api/whatsapp/bulk-send",
        headers=admin_headers,
        json={
            "contacts": ["573001112233", "573002224455"],
            "template": "Hola {custom}",
            "objective": "Recordar cita",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True
    assert payload.get("campaign_id") == "camp_phase5_bulk"
    assert payload.get("successful") == 2
    assert len(captured_bulk) == 2
    assert all(item.get("metadata", {}).get("campaign_id") == "camp_phase5_bulk" for item in captured_bulk)



def test_whatsapp_start_rejects_when_lmstudio_not_running(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime_router, "get_lmstudio_local_models_info", lambda: {"lm_studio_running": False, "models": []})

    response = client.post("/api/whatsapp/start", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is False
    assert "lm studio" in payload.get("error", "").lower()



def test_whatsapp_start_rejects_when_no_models_loaded(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime_router, "get_lmstudio_local_models_info", lambda: {"lm_studio_running": True, "models": []})

    response = client.post("/api/whatsapp/start", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is False
    assert "no hay modelos" in payload.get("error", "").lower()
