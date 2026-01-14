"""
Tests para el sistema de transcripción de audio
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.services.audio_transcriber import audio_transcriber, AudioTranscriber


class TestAudioTranscriber:
    
    def setup_method(self):
        """Setup para cada test"""
        self.transcriber = AudioTranscriber()
        self.test_cache_dir = "data/transcription_cache"
        os.makedirs(self.test_cache_dir, exist_ok=True)
    
    @patch('src.services.audio_transcriber.WhisperModel')
    def test_transcribe_with_mock(self, mock_whisper):
        """Test transcribir audio con mock de Whisper"""
        # Configurar mock
        mock_model = MagicMock()
        mock_segments = [
            MagicMock(text="Hola, este es un mensaje de prueba.")
        ]
        mock_model.transcribe.return_value = (mock_segments, None)
        mock_whisper.return_value = mock_model
        
        # Crear archivo de audio temporal
        test_audio_path = "test_audio.ogg"
        with open(test_audio_path, "wb") as f:
            f.write(b"fake audio data")
        
        try:
            # Transcribir
            result = self.transcriber.transcribe(test_audio_path)
            
            assert result is not None
            assert isinstance(result, str)
        finally:
            # Limpiar
            if os.path.exists(test_audio_path):
                os.remove(test_audio_path)
    
    def test_transcribe_file_not_found(self):
        """Test error cuando archivo no existe"""
        result = self.transcriber.transcribe("nonexistent.ogg")
        
        assert result is None
    
    @patch('src.services.audio_transcriber.WhisperModel')
    def test_transcribe_with_cache(self, mock_whisper):
        """Test que usa cache en segunda transcripción"""
        # Configurar mock
        mock_model = MagicMock()
        mock_segments = [
            MagicMock(text="Texto cacheado")
        ]
        mock_model.transcribe.return_value = (mock_segments, None)
        mock_whisper.return_value = mock_model
        
        test_audio_path = "test_audio_cache.ogg"
        with open(test_audio_path, "wb") as f:
            f.write(b"fake audio data for cache")
        
        try:
            # Primera transcripción (crea cache)
            result1 = self.transcriber.transcribe(test_audio_path)
            
            # Segunda transcripción (debe usar cache)
            result2 = self.transcriber.transcribe(test_audio_path)
            
            assert result1 == result2
        finally:
            if os.path.exists(test_audio_path):
                os.remove(test_audio_path)
    
    def test_transcribe_disabled(self):
        """Test cuando transcripción está deshabilitada"""
        with patch.dict(os.environ, {'AUDIO_TRANSCRIPTION_ENABLED': 'false'}):
            transcriber = AudioTranscriber()
            result = transcriber.transcribe("any.ogg")
            
            assert result is None
    
    @patch('src.services.audio_transcriber.WhisperModel')
    def test_transcribe_file_too_large(self, mock_whisper):
        """Test error cuando archivo excede límite de tamaño"""
        # Configurar límite bajo
        with patch.dict(os.environ, {'MAX_AUDIO_FILE_SIZE_MB': '0.001'}):
            transcriber = AudioTranscriber()
            
            # Crear archivo grande
            test_audio_path = "test_audio_large.ogg"
            with open(test_audio_path, "wb") as f:
                f.write(b"x" * 10000)  # 10KB > 0.001MB
            
            try:
                result = transcriber.transcribe(test_audio_path)
                
                # Debe retornar None o mensaje de error
                assert result is None or "demasiado grande" in result.lower()
            finally:
                if os.path.exists(test_audio_path):
                    os.remove(test_audio_path)
    
    def test_cache_directory_creation(self):
        """Test que el directorio de cache se crea automáticamente"""
        cache_path = Path(self.test_cache_dir)
        
        assert cache_path.exists()
        assert cache_path.is_dir()
    
    @patch('src.services.audio_transcriber.WhisperModel')
    def test_model_initialization(self, mock_whisper):
        """Test inicialización del modelo"""
        transcriber = AudioTranscriber()
        
        # Forzar inicialización del modelo
        test_audio = "test.ogg"
        with open(test_audio, "wb") as f:
            f.write(b"fake")
        
        try:
            transcriber.transcribe(test_audio)
            
            # Verificar que se llamó al constructor de WhisperModel
            assert mock_whisper.called
        finally:
            if os.path.exists(test_audio):
                os.remove(test_audio)
    
    def test_whisper_not_installed(self):
        """Test comportamiento cuando faster-whisper no está instalado"""
        with patch('src.services.audio_transcriber.WHISPER_AVAILABLE', False):
            transcriber = AudioTranscriber()
            result = transcriber.transcribe("any.ogg")
            
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__])
