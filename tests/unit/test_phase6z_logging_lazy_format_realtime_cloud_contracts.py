"""Phase 6Z contracts for lazy logging migration in realtime metrics and cloud provider."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_realtime_metrics_uses_lazy_logging_on_websocket_and_error_paths() -> None:
    text = _read("src/services/realtime_metrics.py")

    assert "logger.info(\"✅ Cliente WebSocket conectado (total: %s)\", len(self.active_connections))" in text
    assert "logger.info(\"❌ Cliente WebSocket desconectado (total: %s)\", len(self.active_connections))" in text
    assert "logger.error(\"❌ Error en loop de broadcast: %s\", e)" in text
    assert "logger.error(\"❌ Error registrando LLM: %s\", e)" in text


def test_whatsapp_cloud_provider_uses_lazy_logging_for_send_receive_media_paths() -> None:
    text = _read("src/services/whatsapp_cloud_provider.py")

    assert "logger.info(\"✅ Mensaje enviado via Cloud API: %s\", message_id)" in text
    assert "logger.error(\"❌ Error Cloud API: %s\", error_msg)" in text
    assert "logger.info(\"🎤 Audio transcrito para %s\", chat_id)" in text
    assert "logger.error(\"❌ Error descargando media: %s\", media_text)" in text
    assert "logger.error(\"❌ Error verificando disponibilidad Cloud API: %s\", e)" in text
