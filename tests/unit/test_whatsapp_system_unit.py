import pytest

from src.services.whatsapp_system import WhatsAppManager

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("contact_name", "expected"),
    [
        ("+57 300 123 4567", "+573001234567"),
        ("300-123-4567", "3001234567"),
        ("Cliente sin teléfono", None),
    ],
)
def test_extract_phone_from_chat(contact_name: str, expected: str | None) -> None:
    manager = WhatsAppManager()
    assert manager._extract_phone_from_chat(contact_name) == expected


@pytest.mark.asyncio
async def test_generate_response_fallback_without_business_config() -> None:
    manager = WhatsAppManager(business_config_manager=None, multi_llm=None)
    response = await manager._generate_response("chat-1", "hola")
    assert "Gracias por tu mensaje" in (response or "")


@pytest.mark.asyncio
async def test_generate_response_uses_multi_llm_result() -> None:
    class FakeConfig:
        config = {"business_info": {"greeting": "Hola"}}

        @staticmethod
        def _build_main_prompt(_cfg):
            return "prompt"

    class FakeLLM:
        async def generate_response(self, messages, inject_contexts=True):
            assert inject_contexts is True
            assert isinstance(messages, list)
            return {"success": True, "response": "respuesta IA"}

    manager = WhatsAppManager(business_config_manager=FakeConfig(), multi_llm=FakeLLM())
    manager.active_chats["chat-1"] = {"messages": []}

    response = await manager._generate_response("chat-1", "hola")
    assert response == "respuesta IA"
