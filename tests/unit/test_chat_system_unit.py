import json

import pytest

from src.services.chat_system import ChatConnectionManager


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent_messages: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, payload: str) -> None:
        self.sent_messages.append(json.loads(payload))


@pytest.mark.asyncio
async def test_connect_creates_session_and_sends_system_message() -> None:
    manager = ChatConnectionManager()
    websocket = FakeWebSocket()

    await manager.connect(websocket, session_id="chat-1")

    assert websocket.accepted is True
    assert len(manager.active_connections) == 1
    assert "chat-1" in manager.chat_sessions
    assert websocket.sent_messages[0]["type"] == "system"


@pytest.mark.asyncio
async def test_process_message_records_user_and_bot_messages(monkeypatch) -> None:
    manager = ChatConnectionManager()
    websocket = FakeWebSocket()
    await manager.connect(websocket, session_id="chat-42")

    async def _fake_generate_bot_response(session_id: str, user_message: str) -> str:
        assert session_id == "chat-42"
        assert user_message == "hola"
        return "respuesta de prueba"

    monkeypatch.setattr(manager, "generate_bot_response", _fake_generate_bot_response)

    await manager.process_message("chat-42", "hola", websocket)

    history = manager.chat_sessions["chat-42"]["messages"]
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"

    sent_types = [msg.get("type") for msg in websocket.sent_messages]
    assert "user_message" in sent_types
    assert "typing" in sent_types
    assert "bot_message" in sent_types
