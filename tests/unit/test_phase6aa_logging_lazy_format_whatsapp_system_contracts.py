"""Phase 6AA contracts for lazy logging migration in whatsapp_system module."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_whatsapp_system_uses_lazy_logging_for_core_runtime_paths() -> None:
    text = _read("src/services/whatsapp_system.py")

    assert "logger.error(\"Error iniciando WhatsApp bot: %s\", e)" in text
    assert "logger.error(\"Error deteniendo WhatsApp bot: %s\", e)" in text
    assert "logger.error(\"Error en loop de mensajes: %s\", e)" in text
    assert "logger.info(\"📸 Detectada imagen en mensaje de %s\", contact_name)" in text
    assert "logger.info(\"Procesando mensaje de %s: %s...\", contact_name, message_text[:100])" in text
    assert "logger.info(\"Respuesta enviada a %s: %s...\", contact_name, response[:100])" in text
    assert "logger.info(\"✅ Imagen descargada: %.2fKB\", len(decoded_bytes) / 1024)" in text
    assert "logger.error(\"Error enviando mensaje: %s\", e)" in text
