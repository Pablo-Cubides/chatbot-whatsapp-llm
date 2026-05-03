"""Test crítico: los modelos por defecto deben ser vigentes (no retirados).

Este test atrapa regresiones donde alguien vuelve a poner modelos retirados como
gpt-4o-mini, claude-3-haiku-20240307, gemini-1.5-flash, grok-beta, etc.

Si un modelo nuevo se retira, añadirlo a la lista RETIRED_MODELS.
"""

from __future__ import annotations

import importlib

import pytest

# Modelos retirados o desaconsejados para producción a la fecha.
RETIRED_MODELS = {
    "gpt-4o-mini",  # Retirado 13 Feb 2026
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-16k",
    "gpt-4",
    "gpt-4-32k",
    "claude-3-haiku-20240307",  # Claude 3 generación 2024
    "claude-3-sonnet-20240229",
    "claude-3-opus-20240229",
    "claude-3-5-sonnet-20241022",
    "gemini-1.5-flash",  # Se desactiva 1 Jun 2026
    "gemini-1.5-pro",
    "gemini-2.0-flash",
    "gemini-pro",
    "grok-beta",  # Modelo de 2024
    "grok-vision-beta",
}


@pytest.fixture()
def fresh_provider_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Asegura que los providers se inicialicen con keys de prueba para que
    su rama se construya y podamos leer el modelo por defecto."""
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("CLAUDE_API_KEY", "test")
    monkeypatch.setenv("XAI_API_KEY", "test")
    # Evitar que un valor de .env contamine el default que queremos verificar
    for k in ("GEMINI_MODEL", "OPENAI_MODEL", "CLAUDE_MODEL", "XAI_MODEL"):
        monkeypatch.delenv(k, raising=False)


def _load_providers():
    """Importa multi_provider_llm con módulo recargado para tomar env actual."""
    from src.services import multi_provider_llm as mpl

    importlib.reload(mpl)
    manager = mpl.MultiProviderLLM()
    return manager.providers, mpl.LLMProvider


def test_no_retired_models_in_provider_defaults(fresh_provider_keys: None) -> None:
    """Cada provider configurado debe tener un model que no esté retirado."""
    providers, LLMProvider = _load_providers()

    failing: list[tuple[str, str]] = []
    for provider, cfg in providers.items():
        if cfg.model in RETIRED_MODELS:
            failing.append((provider.value, cfg.model))

    assert not failing, (
        f"Modelos retirados detectados como default en multi_provider_llm.py: {failing}. Actualizar a un modelo vigente."
    )


def test_gemini_default_is_current(fresh_provider_keys: None) -> None:
    providers, LLMProvider = _load_providers()
    cfg = providers.get(LLMProvider.GEMINI)
    assert cfg is not None
    assert cfg.model.startswith("gemini-2.5") or cfg.model.startswith("gemini-3"), (
        f"Gemini default debe ser 2.5+ o 3.x, no {cfg.model}"
    )


def test_openai_default_is_current(fresh_provider_keys: None) -> None:
    providers, LLMProvider = _load_providers()
    cfg = providers.get(LLMProvider.OPENAI)
    assert cfg is not None
    assert cfg.model.startswith("gpt-5"), f"OpenAI default debe ser gpt-5.x, no {cfg.model} (gpt-4o-mini fue retirado)"


def test_claude_default_is_current(fresh_provider_keys: None) -> None:
    providers, LLMProvider = _load_providers()
    cfg = providers.get(LLMProvider.CLAUDE)
    assert cfg is not None
    assert "haiku-4" in cfg.model or "sonnet-4" in cfg.model or "opus-4" in cfg.model, (
        f"Claude default debe ser generación 4.x, no {cfg.model}"
    )


def test_xai_default_is_current(fresh_provider_keys: None) -> None:
    providers, LLMProvider = _load_providers()
    cfg = providers.get(LLMProvider.XAI)
    assert cfg is not None
    assert cfg.model.startswith("grok-4"), f"xAI default debe ser grok-4.x, no {cfg.model} (grok-beta es de 2024)"


def test_provider_can_be_overridden_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Override por env var debe funcionar (regresión de la lectura de os.getenv)."""
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
    providers, LLMProvider = _load_providers()
    cfg = providers.get(LLMProvider.GEMINI)
    assert cfg is not None
    assert cfg.model == "gemini-3.1-flash-lite-preview"
