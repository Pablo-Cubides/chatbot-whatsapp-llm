"""Unit tests for silent transfer manager logic."""

import pytest

import src.services.silent_transfer as silent_transfer_module
from src.services.silent_transfer import SilentTransferManager, TransferReason

pytestmark = pytest.mark.unit


def test_should_transfer_silently_critical_reasons() -> None:
    manager = SilentTransferManager()
    assert manager.should_transfer_silently(TransferReason.SIMPLE_QUESTION_FAIL, "hola") is True
    assert manager.should_transfer_silently(TransferReason.SUSPICION_DETECTED, "eres un bot?") is True


def test_should_transfer_silently_context_driven() -> None:
    manager = SilentTransferManager()
    assert (
        manager.should_transfer_silently(
            TransferReason.HIGH_VALUE_CLIENT,
            "quiero comprar",
            context={"client_value": 2000},
        )
        is True
    )
    assert (
        manager.should_transfer_silently(
            TransferReason.NEGATIVE_EMOTION,
            "estoy molesto",
            context={"emotion_score": 0.1},
        )
        is True
    )


def test_create_transfer_returns_none_when_db_unavailable(monkeypatch) -> None:
    manager = SilentTransferManager()
    monkeypatch.setattr(silent_transfer_module, "get_session", None)
    transfer_id = manager.create_transfer(
        chat_id="chat-1",
        reason=TransferReason.CRITICAL_ERROR,
        trigger_message="fallo general",
    )
    assert transfer_id is None


def test_reason_explanation_contains_expected_text() -> None:
    manager = SilentTransferManager()
    explanation = manager._get_reason_explanation(TransferReason.SUSPICION_DETECTED)
    assert "Cliente sospechó" in explanation
