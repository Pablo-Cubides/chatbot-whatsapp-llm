"""Compatibility entry point for the retired standalone chat application.

The historical routers and worker import ``chat`` from this module. Requests
delegate to the existing provider implementation; no canned reply is returned.
"""

import asyncio

from src.services.multi_provider_llm import MultiProviderLLM


async def _generate(message: str, chat_id: str, history: list[dict[str, str]]) -> str:
    # A fresh manager keeps aiohttp sessions in the request's event loop, including
    # calls from the synchronous WhatsApp worker and FastAPI's thread pool.
    manager = MultiProviderLLM()
    await manager.initialize()
    messages = [dict(item) for item in history]
    messages.append({"role": "user", "content": message})
    result = await manager.generate_response(messages, business_context={"chat_id": chat_id})
    if not result.get("success") or not isinstance(result.get("response"), str) or not result["response"].strip():
        raise RuntimeError("No language model is available; configure a provider before sending messages.")
    return result["response"]


def chat(message: str, chat_id: str, history: list[dict[str, str]] | None = None) -> str:
    """Generate a reply from synchronous workers or an API thread-pool task."""
    return asyncio.run(_generate(message, chat_id, history or []))
