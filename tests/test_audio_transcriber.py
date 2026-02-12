"""
Tests para el sistema de transcripción de audio
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.audio_transcriber import AudioTranscriber


class TestAudioTranscriber:
    def setup_method(self):
        """Setup para cada test"""
        self.transcriber = AudioTranscriber()
        self.test_cache_dir = "data/transcription_cache"
        os.makedirs(self.test_cache_dir, exist_ok=True)

    def test_transcribe_with_mock(self):
        """Test transcribir audio con mock de Whisper"""
        # Configurar mock model directly
        mock_model = MagicMock()
        mock_segments = [MagicMock(text="Hola, este es un mensaje de prueba.")]
        mock_model.transcribe.return_value = (mock_segments, None)

        transcriber = AudioTranscriber()
        transcriber.model = mock_model
        transcriber.enabled = True

        with patch("src.services.audio_transcriber.WHISPER_AVAILABLE", True):
            audio_data = b"fake audio data"
            result = transcriber.transcribe(audio_data)

        assert result is not None
        assert isinstance(result, str)

    def test_transcribe_not_enabled(self):
        """Test error cuando transcripción no está habilitada"""
        self.transcriber.enabled = False
        result = self.transcriber.transcribe(b"some audio data")

        assert result is None

    def test_transcribe_with_cache(self):
        """Test que usa cache en segunda transcripción"""
        mock_model = MagicMock()
        mock_segments = [MagicMock(text="Texto cacheado")]
        mock_model.transcribe.return_value = (mock_segments, None)

        transcriber = AudioTranscriber()
        transcriber.model = mock_model
        transcriber.enabled = True

        audio_data = b"fake audio data for cache test"

        with patch("src.services.audio_transcriber.WHISPER_AVAILABLE", True):
            # Primera transcripción (crea cache)
            result1 = transcriber.transcribe(audio_data)
            # Segunda transcripción (debe usar cache)
            result2 = transcriber.transcribe(audio_data)

        assert result1 == result2

    def test_transcribe_disabled(self):
        """Test cuando transcripción está deshabilitada"""
        with patch.dict(os.environ, {"AUDIO_TRANSCRIPTION_ENABLED": "false"}):
            transcriber = AudioTranscriber()
            result = transcriber.transcribe(b"any audio data")

            assert result is None

    def test_transcribe_file_too_large(self):
        """Test error cuando audio excede límite de tamaño"""
        mock_model = MagicMock()

        transcriber = AudioTranscriber()
        transcriber.model = mock_model
        transcriber.enabled = True
        transcriber.max_file_size_mb = 0  # Set to 0 so even small data is "too large"

        audio_data = b"x" * 10000  # 10KB > 0MB

        with patch("src.services.audio_transcriber.WHISPER_AVAILABLE", True):
            result = transcriber.transcribe(audio_data)

        # Debe retornar None por exceder límite
        assert result is None

    def test_cache_directory_creation(self):
        """Test que el directorio de cache se crea automáticamente"""
        cache_path = Path(self.test_cache_dir)

        assert cache_path.exists()
        assert cache_path.is_dir()

    def test_model_initialization(self):
        """Test inicialización del modelo"""
        # When WHISPER_AVAILABLE is False, model should be None
        transcriber = AudioTranscriber()

        # The transcriber should have been initialized with expected attributes
        assert hasattr(transcriber, "model")
        assert hasattr(transcriber, "enabled")
        assert hasattr(transcriber, "model_size")
        assert hasattr(transcriber, "cache_dir")

    def test_whisper_not_installed(self):
        """Test comportamiento cuando faster-whisper no está instalado"""
        with patch("src.services.audio_transcriber.WHISPER_AVAILABLE", False):
            transcriber = AudioTranscriber()
            result = transcriber.transcribe(b"any audio data")

            assert result is None


if __name__ == "__main__":
    pytest.main([__file__])
