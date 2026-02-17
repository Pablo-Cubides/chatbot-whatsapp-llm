"""Phase 6X contracts for lazy logging format migration in queue and scheduler modules."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_queue_system_uses_lazy_logging_for_representative_events() -> None:
    text = _read("src/services/queue_system.py")

    assert "logger.info(\"✅ Mensaje encolado: %s para %s\", message_id, chat_id)" in text
    assert "logger.error(\"❌ Error encolando mensaje: %s\", e)" in text
    assert "logger.info(\"✅ Campaña creada: %s\", campaign_id)" in text
    assert "logger.error(\"❌ Error actualizando stats de campaña: %s\", e)" in text


def test_scheduler_worker_uses_lazy_logging_for_error_and_signal_paths() -> None:
    text = _read("src/workers/scheduler_worker.py")

    assert "logger.error(\"❌ Error procesando mensajes programados: %s\", e)" in text
    assert "logger.info(\"⚠️ Señal %s recibida\", signum)" in text
