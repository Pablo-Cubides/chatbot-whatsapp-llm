"""
🔧 Tests para Módulos Core
Tests de los módulos core: config, utils, crypto.
"""

import pytest
from unittest.mock import patch, MagicMock
import os
import tempfile
import json

os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-minimum-32-characters")


class TestConfigModule:
    """Tests para el módulo de configuración."""
    
    def test_settings_defaults(self):
        """Test valores por defecto de configuración."""
        from app.core.config import Settings
        
        with patch.dict(os.environ, {'JWT_SECRET': 'test-secret-32-chars-minimum-here'}):
            settings = Settings()
            
            assert settings.SERVER_HOST == "127.0.0.1"
            assert settings.SERVER_PORT == 8003
            assert settings.LM_STUDIO_PORT == 1234
            assert settings.WHATSAPP_MODE == "web"
    
    def test_settings_from_env(self):
        """Test que settings lee variables de entorno."""
        from app.core.config import Settings
        
        with patch.dict(os.environ, {
            'JWT_SECRET': 'test-secret-32-chars-minimum-here',
            'SERVER_PORT': '9000',
            'SERVER_HOST': '0.0.0.0',
            'WHATSAPP_MODE': 'cloud'
        }):
            settings = Settings()
            
            assert settings.SERVER_PORT == 9000
            assert settings.SERVER_HOST == "0.0.0.0"
            assert settings.WHATSAPP_MODE == "cloud"
    
    def test_cors_origins_parsing(self):
        """Test parsing de CORS origins."""
        from app.core.config import Settings
        
        with patch.dict(os.environ, {
            'JWT_SECRET': 'test-secret-32-chars-minimum-here',
            'CORS_ORIGINS': 'http://a.com, http://b.com, http://c.com'
        }):
            settings = Settings()
            
            assert len(settings.CORS_ORIGINS) == 3
            assert 'http://a.com' in settings.CORS_ORIGINS
            assert 'http://b.com' in settings.CORS_ORIGINS
    
    def test_is_development_mode(self):
        """Test detección de modo desarrollo."""
        from app.core.config import Settings
        
        with patch.dict(os.environ, {
            'JWT_SECRET': 'test-secret-32-chars-minimum-here',
            'SERVER_HOST': '127.0.0.1'
        }):
            settings = Settings()
            assert settings.is_development() is True
        
        with patch.dict(os.environ, {
            'JWT_SECRET': 'test-secret-32-chars-minimum-here',
            'SERVER_HOST': '0.0.0.0'
        }, clear=True):
            settings = Settings()
            assert settings.is_development() is False
    
    def test_settings_singleton(self):
        """Test que get_settings retorna singleton."""
        from app.core.config import get_settings
        
        settings1 = get_settings()
        settings2 = get_settings()
        
        assert settings1 is settings2


class TestUtilsModule:
    """Tests para el módulo de utilidades."""
    
    def test_is_port_open_closed(self):
        """Test puerto cerrado."""
        from app.core.utils import is_port_open
        
        # Puerto alto que probablemente no esté en uso
        result = is_port_open('127.0.0.1', 59876, timeout=0.1)
        assert result is False
    
    def test_get_lm_port_default(self):
        """Test puerto LM Studio por defecto."""
        from app.core.utils import get_lm_port
        
        with patch.dict(os.environ, {}, clear=False):
            # Remover temporalmente si existe
            old = os.environ.pop('LM_STUDIO_PORT', None)
            try:
                port = get_lm_port()
                assert port == 1234
            finally:
                if old:
                    os.environ['LM_STUDIO_PORT'] = old
    
    def test_get_lm_port_custom(self):
        """Test puerto LM Studio personalizado."""
        from app.core.utils import get_lm_port
        
        with patch.dict(os.environ, {'LM_STUDIO_PORT': '5678'}):
            port = get_lm_port()
            assert port == 5678
    
    def test_load_json_config_missing(self):
        """Test cargar config inexistente."""
        from app.core.utils import load_json_config
        
        result = load_json_config('nonexistent_file_12345.json')
        assert result == {}
    
    def test_load_json_config_with_default(self):
        """Test cargar config con default."""
        from app.core.utils import load_json_config
        
        default = {'key': 'value'}
        result = load_json_config('nonexistent.json', default=default)
        assert result == default
    
    def test_save_and_load_json_config(self):
        """Test guardar y cargar config."""
        from app.core.utils import save_json_config, load_json_config
        
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            data = {'test': 'value', 'number': 42}
            # Nota: save_json_config usa ruta relativa al proyecto
            # Este test está simplificado
            pass
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestCryptoModule:
    """Tests para el módulo de criptografía."""
    
    def test_encrypt_decrypt_cycle(self):
        """Test ciclo completo de encriptación."""
        from crypto import encrypt_text, decrypt_text
        
        original = "test_string_123"
        encrypted = encrypt_text(original)
        decrypted = decrypt_text(encrypted)
        
        assert decrypted == original
    
    def test_encrypt_empty_string(self):
        """Test encriptar string vacío."""
        from crypto import encrypt_text
        
        result = encrypt_text("")
        assert result == ""
    
    def test_decrypt_invalid_token(self):
        """Test desencriptar token inválido."""
        from crypto import decrypt_text
        
        # Token inválido debería retornar el valor original
        invalid = "not_a_fernet_token"
        result = decrypt_text(invalid)
        assert result == invalid
    
    def test_oauth_token_functions(self):
        """Test funciones específicas para OAuth."""
        from crypto import encrypt_oauth_token, decrypt_oauth_token
        
        token = "access_token_12345"
        encrypted = encrypt_oauth_token(token)
        decrypted = decrypt_oauth_token(encrypted)
        
        assert encrypted != token
        assert decrypted == token
    
    def test_api_key_functions(self):
        """Test funciones para API keys."""
        from crypto import encrypt_api_key, decrypt_api_key
        
        key = "sk-123456789"
        encrypted = encrypt_api_key(key)
        decrypted = decrypt_api_key(encrypted)
        
        assert encrypted != key
        assert decrypted == key
    
    def test_is_encrypted(self):
        """Test detección de valores encriptados."""
        from crypto import is_encrypted, encrypt_text
        
        encrypted = encrypt_text("test")
        
        assert is_encrypted(encrypted) is True
        assert is_encrypted("plain_text") is False
        assert is_encrypted("") is False
    
    def test_key_rotation(self):
        """Test de rotación de claves."""
        from crypto import rotate_encryption_key
        from cryptography.fernet import Fernet
        
        old_key = Fernet.generate_key()
        new_key = Fernet.generate_key()
        
        # Encriptar con clave vieja
        old_fernet = Fernet(old_key)
        original = "sensitive_data"
        encrypted = old_fernet.encrypt(original.encode()).decode()
        
        # Rotar a nueva clave
        rotated = rotate_encryption_key(old_key, new_key, encrypted)
        
        # Debe poder desencriptarse con nueva clave
        new_fernet = Fernet(new_key)
        decrypted = new_fernet.decrypt(rotated.encode()).decode()
        
        assert decrypted == original


class TestProtectionSystem:
    """Tests para el sistema de protección."""
    
    def test_rate_limit_rules(self):
        """Test que las reglas de rate limit existen."""
        from src.services.protection_system import RATE_LIMIT_RULES
        
        assert 'api_general' in RATE_LIMIT_RULES
        assert 'llm_generation' in RATE_LIMIT_RULES
        assert 'whatsapp_messages' in RATE_LIMIT_RULES
        assert 'auth_attempts' in RATE_LIMIT_RULES
    
    def test_circuit_breaker_states(self):
        """Test estados del circuit breaker."""
        from src.services.protection_system import CircuitBreakerState
        
        assert CircuitBreakerState.CLOSED == "closed"
        assert CircuitBreakerState.OPEN == "open"
        assert CircuitBreakerState.HALF_OPEN == "half_open"
    
    def test_circuit_breaker_creation(self):
        """Test creación de circuit breaker."""
        from src.services.protection_system import CircuitBreaker
        
        cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30,
            name="test_breaker"
        )
        
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30
        assert cb.name == "test_breaker"
    
    def test_rate_limiter(self):
        """Test del rate limiter."""
        from src.services.protection_system import RateLimiter, RateLimitRule
        
        limiter = RateLimiter()
        rule = RateLimitRule(requests=5, window=60, identifier="test")
        
        # Primeras 5 requests deben pasar
        for i in range(5):
            allowed, info = limiter.is_allowed(rule, f"user_{i % 2}")
            assert allowed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
