"""Phase 3A async/performance hardening tests."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.routers.chat_core import event_stream
from src.services.multi_provider_llm import LLMProvider, MultiProviderLLM

pytestmark = [pytest.mark.api]


@pytest.mark.asyncio
async def test_llm_initialize_defers_local_provider_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    llm = MultiProviderLLM()

    # On constructor, local providers are registered but disabled (no import-time I/O).
    assert llm.providers[LLMProvider.OLLAMA].active is False
    assert llm.providers[LLMProvider.LM_STUDIO].active is False

    monkeypatch.setattr(llm, "_check_ollama_available_async", AsyncMock(return_value=True))
    monkeypatch.setattr(llm, "_check_lmstudio_available_async", AsyncMock(return_value=False))

    await llm.initialize()

    assert llm.providers[LLMProvider.OLLAMA].active is True
    assert llm.providers[LLMProvider.LM_STUDIO].active is False


@pytest.mark.asyncio
async def test_llm_uses_injected_shared_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    llm = MultiProviderLLM()
    config = llm.providers[LLMProvider.OPENAI]

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 1}})

    mock_post_cm = AsyncMock()
    mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_cm.__aexit__ = AsyncMock(return_value=False)

    shared_session = MagicMock()
    shared_session.closed = False
    shared_session.post = MagicMock(return_value=mock_post_cm)

    llm.set_http_session(shared_session)

    with patch("aiohttp.ClientSession", side_effect=AssertionError("must not create new session")):
        result = await llm._call_openai(config, [{"role": "user", "content": "hi"}], max_retries=1)

    assert result["success"] is True
    assert shared_session.post.called


@pytest.mark.asyncio
async def test_api_events_stream_non_blocking() -> None:
    stream = event_stream()
    first = await asyncio.wait_for(anext(stream), timeout=2)
    assert isinstance(first, str)
    assert "data:" in first
    await stream.aclose()
