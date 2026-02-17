"""
🧪 Tests de integración para endpoints de API
Verifica el funcionamiento de los endpoints de producción via admin_panel.
"""

import os
import sys
import types

import pytest

# Configurar variables de entorno para tests
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-minimum-32-characters")
os.environ.setdefault("ADMIN_PASSWORD", "test_admin_password")

# Provide a stub_chat module so admin_panel can import it
if "stub_chat" not in sys.modules:
    _stub = types.ModuleType("stub_chat")
    _stub.chat = lambda *a, **kw: "stub response"
    sys.modules["stub_chat"] = _stub

from fastapi.testclient import TestClient

pytestmark = pytest.mark.api


class TestAuthEndpoints:
    """Tests para los endpoints de autenticación."""

    @pytest.fixture
    def client(self):
        """Cliente de prueba para FastAPI."""
        from admin_panel import app

        return TestClient(app)

    @pytest.fixture
    def auth_token(self, client):
        """Obtiene un token de autenticación para tests."""
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": os.environ.get("ADMIN_PASSWORD", "test_admin_password")},
        )
        assert response.status_code == 200
        return response.json()["access_token"]

    @pytest.mark.parametrize(
        ("path", "expected_key"),
        [("/healthz", "status"), ("/", "status")],
    )
    def test_public_endpoints(self, client, path, expected_key):
        """Los endpoints públicos clave deben responder OK."""
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert expected_key in data

    def test_unauthorized_without_token(self, client):
        """Test que endpoints protegidos requieren token."""
        response = client.get("/models")
        assert response.status_code == 401


class TestQueueEndpoints:
    """Tests para los endpoints de cola de mensajes."""

    def test_queue_system_import(self):
        """Test que el sistema de cola se puede importar."""
        from src.services.queue_system import queue_manager

        assert queue_manager is not None

    def test_queue_manager_methods(self):
        """Test que queue_manager tiene los métodos esperados."""
        from src.services.queue_system import queue_manager

        assert hasattr(queue_manager, "enqueue_message")
        assert hasattr(queue_manager, "get_pending_messages")
        assert hasattr(queue_manager, "mark_as_sent")
        assert hasattr(queue_manager, "mark_as_failed")


class TestAlertEndpoints:
    """Tests para los endpoints de alertas."""

    def test_alert_system_import(self):
        """Test que el sistema de alertas se puede importar."""
        from src.services.alert_system import alert_manager

        assert alert_manager is not None

    def test_alert_manager_methods(self):
        """Test que alert_manager tiene los métodos esperados."""
        from src.services.alert_system import alert_manager

        assert hasattr(alert_manager, "get_alerts")
        assert hasattr(alert_manager, "create_alert")
        assert hasattr(alert_manager, "check_alert_rules")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
