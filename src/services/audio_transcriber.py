"""
🎤 Audio Transcriber - Transcripción local con faster-whisper
Convierte audio/voice notes a texto usando IA local
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Importación condicional de faster-whisper
try:
    from faster_whisper import WhisperModel

    WHISPER_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ faster-whisper no disponible. Instalar con: pip install faster-whisper")
    WHISPER_AVAILABLE = False


class AudioTranscriber:
    """Transcriptor de audio usando faster-whisper"""

    def __init__(self):
        self.enabled = os.environ.get("AUDIO_TRANSCRIPTION_ENABLED", "true").lower() == "true"
        self.model_size = os.environ.get("WHISPER_MODEL_SIZE", "base")  # tiny, base, small, medium, large
        self.device = os.environ.get("WHISPER_DEVICE", "cpu")  # cpu, cuda
        self.model = None
        self.cache_dir = Path("data/transcription_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Límites
        self.max_file_size_mb = int(os.environ.get("MAX_AUDIO_FILE_SIZE_MB", "10"))
        self.max_duration_seconds = int(os.environ.get("MAX_AUDIO_DURATION_SECONDS", "300"))  # 5 min

        if self.enabled and WHISPER_AVAILABLE:
            logger.info("🎤 AudioTranscriber inicializando (model=%s, device=%s)", self.model_size, self.device)
            self._initialize_model()
        elif self.enabled and not WHISPER_AVAILABLE:
            logger.warning("⚠️ Transcripción habilitada pero faster-whisper no disponible")
        else:
            logger.info("🔇 Transcripción de audio deshabilitada")

    def _initialize_model(self):
        """Inicializar modelo de Whisper"""
        try:
            self.model = WhisperModel(
                self.model_size, device=self.device, compute_type="int8" if self.device == "cpu" else "float16"
            )
            logger.info("✅ Modelo Whisper '%s' cargado", self.model_size)
        except Exception as e:
            logger.error("❌ Error cargando modelo Whisper: %s", e)
            self.enabled = False

    def transcribe(self, audio_bytes: bytes, language: str = "es", audio_id: Optional[str] = None) -> Optional[str]:
        """
        Transcribir audio a texto

        Args:
            audio_bytes: Bytes del archivo de audio
            language: Código de idioma (es, en, etc.)
            audio_id: ID del audio para caché

        Returns:
            Texto transcrito o None si falla
        """
        if not self.enabled or not WHISPER_AVAILABLE or not self.model:
            logger.warning("⚠️ Transcripción no disponible")
            return None

        try:
            # Verificar tamaño
            size_mb = len(audio_bytes) / (1024 * 1024)
            if size_mb > self.max_file_size_mb:
                logger.warning("⚠️ Audio demasiado grande: %.2fMB > %sMB", size_mb, self.max_file_size_mb)
                return None

            # Verificar caché
            cache_key = self._get_cache_key(audio_bytes)
            cached_text = self._get_from_cache(cache_key)

            if cached_text:
                logger.info("✅ Transcripción desde caché: %s...", cache_key[:8])
                return cached_text

            # Guardar temporalmente
            temp_audio_path = self.cache_dir / f"temp_{cache_key}.ogg"
            with open(temp_audio_path, "wb") as f:
                f.write(audio_bytes)

            # Transcribir
            logger.info("🎤 Transcribiendo audio (%.2fMB)...", size_mb)

            segments, info = self.model.transcribe(
                str(temp_audio_path),
                language=language,
                beam_size=5,
                vad_filter=True,  # Voice Activity Detection
            )

            # Concatenar segmentos
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            transcribed_text = " ".join(text_parts).strip()

            # Limpiar archivo temporal
            temp_audio_path.unlink()

            if not transcribed_text:
                logger.warning("⚠️ No se detectó voz en el audio")
                return None

            # Guardar en caché
            self._save_to_cache(cache_key, transcribed_text)

            logger.info("✅ Audio transcrito: %s caracteres", len(transcribed_text))
            logger.debug("Texto: %s...", transcribed_text[:100])

            return transcribed_text

        except Exception as e:
            logger.error("❌ Error transcribiendo audio: %s", e)
            # Limpiar archivo temporal si existe
            try:
                if temp_audio_path and temp_audio_path.exists():
                    temp_audio_path.unlink()
            except OSError:
                pass
            return None

    def _get_cache_key(self, audio_bytes: bytes) -> str:
        """Generar clave de caché usando hash del audio"""
        return hashlib.sha256(audio_bytes).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """Obtener transcripción desde caché"""
        cache_file = self.cache_dir / f"{cache_key}.txt"

        try:
            if cache_file.exists():
                with open(cache_file, encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            logger.warning("⚠️ Error leyendo caché: %s", e)

        return None

    def _save_to_cache(self, cache_key: str, text: str):
        """Guardar transcripción en caché"""
        cache_file = self.cache_dir / f"{cache_key}.txt"

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            logger.warning("⚠️ Error guardando en caché: %s", e)

    def clear_cache(self):
        """Limpiar caché de transcripciones"""
        try:
            for cache_file in self.cache_dir.glob("*.txt"):
                cache_file.unlink()
            logger.info("🗑️ Caché de transcripciones limpiado")
        except Exception as e:
            logger.error("❌ Error limpiando caché: %s", e)

    def get_stats(self) -> dict:
        """Obtener estadísticas del transcriptor"""
        cache_files = list(self.cache_dir.glob("*.txt"))

        return {
            "enabled": self.enabled,
            "available": WHISPER_AVAILABLE and self.model is not None,
            "model_size": self.model_size,
            "device": self.device,
            "max_file_size_mb": self.max_file_size_mb,
            "cached_transcriptions": len(cache_files),
        }


# Instancia global
audio_transcriber = AudioTranscriber()
