import pytest

from src.services.image_analyzer import ImageAnalyzer


@pytest.mark.asyncio
async def test_analyze_image_uses_cache_after_first_success(monkeypatch) -> None:
    analyzer = ImageAnalyzer()
    analyzer.enabled = True
    analyzer.gemini_key = "test-key"
    analyzer.openai_key = None

    call_count = {"gemini": 0}

    async def _fake_gemini(image_bytes: bytes, prompt: str):
        call_count["gemini"] += 1
        return {
            "success": True,
            "description": "una taza de café sobre la mesa",
            "provider": "gemini",
            "cached": False,
        }

    monkeypatch.setattr(analyzer, "_analyze_with_gemini", _fake_gemini)

    first = await analyzer.analyze_image(b"image-bytes", context="cliente preguntó por menú")
    second = await analyzer.analyze_image(b"image-bytes", context="cliente preguntó por menú")

    assert first["success"] is True
    assert first["cached"] is False
    assert second["success"] is True
    assert second["cached"] is True
    assert second["description"] == "una taza de café sobre la mesa"
    assert call_count["gemini"] == 1


@pytest.mark.asyncio
async def test_analyze_image_rejects_oversized_payload() -> None:
    analyzer = ImageAnalyzer()
    analyzer.enabled = True
    analyzer.max_image_size_mb = 1

    too_large = b"x" * (2 * 1024 * 1024)
    result = await analyzer.analyze_image(too_large)

    assert result["success"] is False
    assert "Imagen muy grande" in result["error"]


def test_build_analysis_prompt_includes_context_and_recent_history() -> None:
    analyzer = ImageAnalyzer()
    prompt = analyzer._build_analysis_prompt(
        context="Cliente quiere reservar una mesa",
        conversation_history=[
            {"role": "user", "content": "hola"},
            {"role": "assistant", "content": "¡hola!"},
            {"role": "user", "content": "te envío una foto"},
        ],
    )

    assert "Contexto de la conversación" in prompt
    assert "Cliente quiere reservar una mesa" in prompt
    assert "Últimos mensajes" in prompt
    assert "user: te envío una foto" in prompt
