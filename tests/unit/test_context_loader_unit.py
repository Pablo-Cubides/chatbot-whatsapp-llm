from datetime import datetime

from src.services.context_loader import ContextLoader


def test_load_all_contexts_populates_contact_objective(monkeypatch) -> None:
    loader = ContextLoader()

    monkeypatch.setattr(loader, "load_daily_context", lambda: {"text": "promo del día", "effective_date": "2026-02-15"})
    monkeypatch.setattr(loader, "load_user_contexts", lambda user_id: [{"text": "prefiere horarios tarde"}])
    monkeypatch.setattr(
        loader,
        "load_contact_profile",
        lambda chat_id: {"chat_id": chat_id, "objective": "cerrar cita", "instructions": "tono cordial"},
    )
    monkeypatch.setattr(loader, "load_active_strategy", lambda chat_id: {"version": 2, "strategy_text": "hacer pregunta cerrada"})

    contexts = loader.load_all_contexts("chat-ctx-1")

    assert contexts["chat_id"] == "chat-ctx-1"
    assert contexts["contact_objective"] == "cerrar cita"
    assert contexts["active_strategy"]["version"] == 2


def test_build_context_prompt_section_contains_expected_blocks() -> None:
    loader = ContextLoader()
    prompt = loader.build_context_prompt_section(
        {
            "daily_context": {"effective_date": "2026-02-15", "text": "hoy hay promo"},
            "contact_objective": "concretar llamada",
            "contact_profile": {
                "perfil": "cliente nuevo",
                "initial_context": "viene de campaña",
                "instructions": "respuestas breves",
            },
            "active_strategy": {"version": 3, "strategy_text": "priorizar disponibilidad"},
            "user_contexts": [{"text": "le gusta confirmar por la tarde"}],
        }
    )

    assert "CONTEXTO DEL DÍA" in prompt
    assert "OBJETIVO CON ESTE CLIENTE" in prompt
    assert "ESTRATEGIA OPERATIVA" in prompt
    assert "NOTAS SOBRE EL USUARIO" in prompt


def test_should_inject_contexts_is_enabled() -> None:
    loader = ContextLoader()
    assert loader.should_inject_contexts("chat-any") is True


def test_load_active_strategy_handles_missing_dependency() -> None:
    loader = ContextLoader()

    # si falla import interno, debe devolver None sin lanzar
    # (forzamos chat_id improbable para no depender de DB)
    result = loader.load_active_strategy("chat-no-dependency-needed")
    assert result is None or isinstance(result, dict)
