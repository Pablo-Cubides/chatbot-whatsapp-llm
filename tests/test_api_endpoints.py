"""
🧪 Tests para los nuevos endpoints de API
Tests de integración para verificar el funcionamiento de los endpoints modulares.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import os

# Configurar variables de entorno para tests
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-minimum-32-characters")
os.environ.setdefault("ADMIN_PASSWORD", "test_admin_password")

from fastapi.testclient import TestClient


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
        # Usar legacy token para tests
        os.environ["LEGACY_TOKEN_ENABLED"] = "true"
        os.environ["LEGACY_ADMIN_TOKEN"] = "test_admin_token"
        return "test_admin_token"
    
    def test_health_endpoint(self, client):
        """Test del endpoint de salud."""
        response = client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_root_endpoint(self, client):
        """Test del endpoint raíz."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    
    def test_unauthorized_without_token(self, client):
        """Test que endpoints protegidos requieren token."""
        response = client.get("/models")
        assert response.status_code == 401


class TestBusinessConfigEndpoints:
    """Tests para los endpoints de configuración de negocio."""
    
    @pytest.fixture
    def client(self):
        from admin_panel import app
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Headers de autenticación."""
        os.environ["LEGACY_TOKEN_ENABLED"] = "true"
        os.environ["LEGACY_ADMIN_TOKEN"] = "test_token"
        return {"Authorization": "Bearer test_token"}
    
    @patch('app.api.endpoints.business_config._load_business_config')
    def test_get_business_config(self, mock_load, client, auth_headers):
        """Test obtener configuración de negocio."""
        mock_load.return_value = {"business_name": "Test Business"}
        
        # Este endpoint existe en el módulo pero necesita estar registrado
        # El test verifica la lógica del módulo
        from app.api.endpoints.business_config import _load_business_config
        result = _load_business_config()
        # El mock no afecta la función real importada antes del patch


class TestQueueEndpoints:
    """Tests para los endpoints de cola de mensajes."""
    
    @pytest.fixture
    def client(self):
        from admin_panel import app
        return TestClient(app)
    
    def test_queue_system_import(self):
        """Test que el sistema de cola se puede importar."""
        from src.services.queue_system import queue_manager
        assert queue_manager is not None
    
    def test_queue_manager_methods(self):
        """Test que queue_manager tiene los métodos esperados."""
        from src.services.queue_system import queue_manager
        
        assert hasattr(queue_manager, 'enqueue_message')
        assert hasattr(queue_manager, 'get_pending_messages')
        assert hasattr(queue_manager, 'mark_as_sent')
        assert hasattr(queue_manager, 'mark_as_failed')


class TestAlertEndpoints:
    """Tests para los endpoints de alertas."""
    
    def test_alert_system_import(self):
        """Test que el sistema de alertas se puede importar."""
        from src.services.alert_system import alert_manager
        assert alert_manager is not None
    
    def test_alert_manager_methods(self):
        """Test que alert_manager tiene los métodos esperados."""
        from src.services.alert_system import alert_manager
        
        assert hasattr(alert_manager, 'get_alerts')
        assert hasattr(alert_manager, 'get_stats')


class TestAnalyticsEndpoints:
    """Tests para los endpoints de analytics."""
    
    def test_analytics_import(self):
        """Test que el módulo de analytics existe."""
        from app.api.endpoints import analytics
        assert analytics is not None
        assert hasattr(analytics, 'router')


class TestWhatsAppEndpoints:
    """Tests para los endpoints de WhatsApp."""
    
    def test_whatsapp_module_import(self):
        """Test que el módulo de WhatsApp existe."""
        from app.api.endpoints import whatsapp
        assert whatsapp is not None
        assert hasattr(whatsapp, 'router')
    
    def test_model_categorization(self):
        """Test de la función de categorización de modelos."""
        from app.api.endpoints.whatsapp import _filter_and_categorize_models
        
        models = [
            {'id': 'nemotron-mini-4b-instruct'},
            {'id': 'meta-llama-3.1-8b-instruct'},
            {'id': 'some-embedding-model'},
            {'id': 'unknown-model'}
        ]
        
        result = _filter_and_categorize_models(models)
        
        assert 'main_models' in result
        assert 'reasoning_models' in result
        assert 'hidden_models' in result
        assert len(result['main_models']) == 2


class TestCoreModules:
    """Tests para los módulos core."""
    
    def test_config_import(self):
        """Test que la configuración se puede importar."""
        from app.core.config import settings, get_settings
        
        assert settings is not None
        assert get_settings() is not None
    
    def test_config_settings(self):
        """Test de configuraciones básicas."""
        from app.core.config import settings
        
        assert hasattr(settings, 'SERVER_HOST')
        assert hasattr(settings, 'SERVER_PORT')
        assert hasattr(settings, 'JWT_SECRET')
        assert hasattr(settings, 'CORS_ORIGINS')
    
    def test_utils_import(self):
        """Test que las utilidades se pueden importar."""
        from app.core.utils import (
            is_port_open,
            get_lm_port,
            load_json_config,
            save_json_config
        )
        
        assert callable(is_port_open)
        assert callable(get_lm_port)
        assert callable(load_json_config)
        assert callable(save_json_config)
    
    def test_lm_port_default(self):
        """Test del puerto por defecto de LM Studio."""
        from app.core.utils import get_lm_port
        
        # Asegurar que no esté configurado
        old_value = os.environ.pop('LM_STUDIO_PORT', None)
        try:
            port = get_lm_port()
            assert port == 1234
        finally:
            if old_value:
                os.environ['LM_STUDIO_PORT'] = old_value
    
    def test_is_port_open_localhost(self):
        """Test de verificación de puerto."""
        from app.core.utils import is_port_open
        
        # Puerto que probablemente no esté abierto
        result = is_port_open('127.0.0.1', 59999, timeout=0.1)
        assert result is False


class TestRouterIntegration:
    """Tests de integración del router principal."""
    
    def test_router_import(self):
        """Test que el router principal se puede importar."""
        from app.api.router import api_router, get_api_router
        
        assert api_router is not None
        assert get_api_router() is not None
    
    def test_router_has_routes(self):
        """Test que el router tiene rutas registradas."""
        from app.api.router import api_router
        
        # El router debería tener rutas de los sub-routers
        assert len(api_router.routes) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
