"""
🔐 Tests de Seguridad
Tests específicos para verificar seguridad del sistema.
"""

import os
import sys
import types
import importlib
from unittest.mock import patch

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-minimum-32-characters")
os.environ.setdefault("ADMIN_PASSWORD", "test_admin_password")

# Provide a stub_chat module so admin_panel can import it
if "stub_chat" not in sys.modules:
    _stub = types.ModuleType("stub_chat")
    _stub.chat = lambda *a, **kw: "stub response"
    sys.modules["stub_chat"] = _stub

from fastapi.testclient import TestClient


class TestSecurityVulnerabilities:
    """Tests de vulnerabilidades de seguridad."""

    @pytest.fixture
    def client(self):
        from admin_panel import app

        return TestClient(app)

    @pytest.mark.security
    def test_sql_injection_prevention(self, client):
        """Test de protección contra SQL injection en endpoints."""
        # Intentar SQL injection en parámetros
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "1; SELECT * FROM users",
            "admin'--",
        ]

        for payload in malicious_inputs:
            # Estos endpoints deberían manejar input malicioso sin errores SQL
            response = client.get(f"/user-contexts/{payload}")
            # No debería causar error 500 por SQL
            assert response.status_code in [401, 404, 422], f"Posible SQL injection con: {payload}"

    @pytest.mark.security
    def test_xss_prevention(self, client):
        """Test de protección contra XSS."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert(1)>",
            "&#x3C;script&#x3E;alert(1)&#x3C;/script&#x3E;",
            "data:text/html,<script>alert(1)</script>",
            "<a href='javascript:alert(1)'>x</a>",
            "<div onmouseover='alert(1)'>hover</div>",
            "<input onfocus=alert(1) autofocus>",
            "<body onerror=alert(1)>",
            "{{7*7}}",
            "<style>div{background:url(javascript:alert(1))}</style>",
            "<img src=x onerror=&#x61;alert(1)>",
            "%253Cscript%253Ealert(1)%253C/script%253E",
            "<iframe src='javascript:alert(1)'></iframe>",
            "<math><mi xlink:href='data:x,<script>alert(1)</script>'>X</mi></math>",
            "<details open ontoggle=alert(1)>x</details>",
        ]

        for payload in xss_payloads:
            # El sistema no debería reflejar scripts sin sanitizar
            response = client.get(f"/?test={payload}")
            if response.status_code == 200:
                content = response.text
                lowered = content.lower()
                assert payload.lower() not in lowered
                assert "<script" not in lowered
                assert "javascript:alert(" not in lowered

    @pytest.mark.security
    def test_path_traversal_payloads_do_not_succeed(self, client):
        """Test de payloads de path traversal en endpoints representativos."""
        traversal_payloads = [
            "../../etc/passwd",
            "..\\..\\windows\\system32",
            "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%00/..%00/etc/passwd",
        ]

        for payload in traversal_payloads:
            response = client.get(f"/user-contexts/{payload}")
            assert response.status_code in [401, 403, 404, 422], f"Traversal payload inesperado permitido: {payload}"

    @pytest.mark.security
    def test_authentication_required(self, client):
        """Test que endpoints protegidos requieren autenticación."""
        protected_endpoints_get = [
            "/models",
            "/user-contexts/test",
        ]
        protected_endpoints_post = [
            "/rules",
            "/contacts",
        ]

        for endpoint in protected_endpoints_get:
            response = client.get(endpoint)
            assert response.status_code == 401, f"Endpoint GET {endpoint} no requiere auth"

        for endpoint in protected_endpoints_post:
            response = client.post(endpoint)
            assert response.status_code == 401, f"Endpoint POST {endpoint} no requiere auth"

    @pytest.mark.security
    def test_invalid_token_rejected(self, client):
        """Test que tokens inválidos son rechazados."""
        invalid_tokens = [
            "invalid_token",
            "Bearer invalid",
            "null",
            "",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature",
        ]

        for token in invalid_tokens:
            headers = {"Authorization": f"Bearer {token}" if token else ""}
            response = client.get("/models", headers=headers)
            assert response.status_code == 401

    @pytest.mark.security
    def test_jwt_secret_validation(self):
        """Test que JWT secret es validado correctamente."""
        from src.services.auth_system import AuthManager

        # Sin JWT_SECRET debería fallar
        with patch.dict(os.environ, {}, clear=True), pytest.raises(ValueError, match="JWT_SECRET"):
            AuthManager()

    @pytest.mark.security
    def test_password_hashing(self):
        """Test que passwords son hasheados correctamente."""
        from src.services.auth_system import AuthManager

        with patch.dict(
            os.environ, {"JWT_SECRET": "test-secret-minimum-32-characters-long", "ADMIN_PASSWORD": "test_password"}
        ):
            auth = AuthManager()

            # Hash debe ser diferente al password original
            hashed = auth._hash_password("test_password")
            assert hashed != "test_password"
            assert hashed.startswith("$2b$")  # bcrypt format

            # Verificación debe funcionar
            assert auth._verify_password("test_password", hashed)
            assert not auth._verify_password("wrong_password", hashed)

    @pytest.mark.security
    def test_rate_limiting_rules_exist(self):
        """Test que existen reglas de rate limiting."""
        from src.services.protection_system import RATE_LIMIT_RULES

        assert "api_general" in RATE_LIMIT_RULES
        assert "llm_requests" in RATE_LIMIT_RULES
        assert "auth_attempts" in RATE_LIMIT_RULES

        # Auth attempts debe ser restrictivo
        auth_rule = RATE_LIMIT_RULES["auth_attempts"]
        assert auth_rule.requests <= 5  # Máximo 5 intentos


class TestCryptoSecurity:
    """Tests de seguridad para encriptación."""

    @pytest.mark.security
    def test_fernet_encryption(self):
        """Test de encriptación Fernet."""
        from crypto import decrypt_text, encrypt_text

        original = "sensitive_data_123"
        encrypted = encrypt_text(original)

        # Debe ser diferente al original
        assert encrypted != original
        # Debe poder desencriptarse
        decrypted = decrypt_text(encrypted)
        assert decrypted == original

    @pytest.mark.security
    def test_oauth_token_encryption(self):
        """Test de encriptación de tokens OAuth."""
        from crypto import decrypt_oauth_token, encrypt_oauth_token

        token = "ya29.a0AfH6SMC..."  # Simular token OAuth
        encrypted = encrypt_oauth_token(token)

        # Debe estar encriptado
        assert encrypted != token
        assert encrypted.startswith("gAAAAA")  # Fernet format

        # Debe poder desencriptarse
        decrypted = decrypt_oauth_token(encrypted)
        assert decrypted == token

    @pytest.mark.security
    def test_null_token_handling(self):
        """Test manejo de tokens nulos."""
        from crypto import decrypt_oauth_token, encrypt_oauth_token

        assert encrypt_oauth_token(None) is None
        assert decrypt_oauth_token(None) is None

    @pytest.mark.security
    def test_is_encrypted_detection(self):
        """Test de detección de valores encriptados."""
        from crypto import encrypt_text, is_encrypted

        plain = "plain_text"
        encrypted = encrypt_text(plain)

        assert is_encrypted(encrypted) is True
        assert is_encrypted(plain) is False
        assert is_encrypted("") is False
        assert is_encrypted(None) is False


class TestCORSConfiguration:
    """Tests de configuración CORS."""

    @pytest.mark.security
    def test_cors_not_wildcard(self):
        """Test que CORS no permite todos los orígenes en producción."""
        # Leer archivo admin_panel.py y verificar CORS

        # Verificar que hay configuración CORS
        # La configuración ahora usa variables de entorno
        cors_origins = os.environ.get("CORS_ORIGINS", "")
        assert "*" not in cors_origins or not cors_origins

    @pytest.mark.security
    def test_cors_wildcard_is_sanitized_at_runtime(self):
        """Si CORS_ORIGINS='*', la app fuerza orígenes seguros por defecto."""
        import admin_panel

        with patch.dict(os.environ, {"CORS_ORIGINS": "*"}, clear=False):
            importlib.reload(admin_panel)
            app = admin_panel.app
            cors_middlewares = [m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"]
            assert cors_middlewares, "CORSMiddleware no configurado"
            allow_origins = cors_middlewares[0].kwargs.get("allow_origins", [])
            assert "*" not in allow_origins
            assert "http://localhost:8003" in allow_origins

        # Restablecer módulo para no contaminar otros tests
        importlib.reload(admin_panel)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "security"])
