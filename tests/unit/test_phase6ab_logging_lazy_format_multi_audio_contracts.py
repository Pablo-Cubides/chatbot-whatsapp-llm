"""Phase 6AB contracts for lazy logging migration in multi-provider and audio modules."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_audio_transcriber_uses_lazy_logging_for_init_transcribe_and_cache_paths() -> None:
    text = _read("src/services/audio_transcriber.py")

    assert 'logger.info("🎤 AudioTranscriber inicializando (model=%s, device=%s)", self.model_size, self.device)' in text
    assert 'logger.warning("⚠️ Audio demasiado grande: %.2fMB > %sMB", size_mb, self.max_file_size_mb)' in text
    assert 'logger.info("✅ Transcripción desde caché: %s...", cache_key[:8])' in text
    assert 'logger.info("✅ Audio transcrito: %s caracteres", len(transcribed_text))' in text
    assert 'logger.error("❌ Error transcribiendo audio: %s", e)' in text


def test_multi_provider_llm_uses_lazy_logging_for_fallback_and_humanization_paths() -> None:
    text = _read("src/services/multi_provider_llm.py")

    assert 'logger.info("Configurados %s proveedores de IA", len(self.providers))' in text
    assert 'logger.info("Fallback normal: %s", [p.value for p in self.normal_fallback])' in text
    assert 'logger.info("📦 Contextos inyectados para chat %s", chat_id)' in text
    assert 'logger.info("Intentando con proveedor: %s", provider.value)' in text
    assert 'logger.error("❌ NEGACIÓN ÉTICA detectada en %s", provider.value)' in text
    assert 'logger.warning("❌ Error con %s: %s", provider.value, str(e))' in text
    assert 'logger.error("🔇 TRANSFERENCIA SILENCIOSA activada para: %s", user_message[:50])' in text
