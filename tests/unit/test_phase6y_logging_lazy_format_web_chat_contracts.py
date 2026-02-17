"""Phase 6Y contracts for lazy logging format migration in web/chat modules."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_whatsapp_web_provider_uses_lazy_error_logging() -> None:
    text = _read("src/services/whatsapp_web_provider.py")

    assert "logger.error(\"❌ Error enviando mensaje via Web: %s\", e)" in text
    assert "logger.error(\"❌ Error normalizando mensaje Web: %s\", e)" in text
    assert "logger.error(\"❌ Error verificando disponibilidad Web: %s\", e)" in text


def test_chat_system_uses_lazy_error_logging() -> None:
    text = _read("src/services/chat_system.py")

    assert "logger.error(\"Error procesando mensaje: %s\", e)" in text
    assert "logger.error(\"Error generando respuesta: %s\", e)" in text
