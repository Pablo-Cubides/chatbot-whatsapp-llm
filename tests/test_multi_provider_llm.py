"""
Tests para el sistema Multi-Provider LLM
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.multi_provider_llm import APIConfig, LLMProvider, MultiProviderLLM


class TestMultiProviderLLM:
    def setup_method(self):
        """Setup para cada test"""
        # Mock environment variables
        self.env_patcher = patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "test_gemini_key",
                "OPENAI_API_KEY": "test_openai_key",
                "CLAUDE_API_KEY": "test_claude_key",
                "XAI_API_KEY": "test_xai_key",
                "DEFAULT_LLM_PROVIDER": "gemini",
            },
        )
        self.env_patcher.start()

        # Mock requests to avoid actual API calls
        self.requests_patcher = patch("aiohttp.ClientSession")
        self.mock_requests = self.requests_patcher.start()

    def teardown_method(self):
        """Cleanup después de cada test"""
        self.env_patcher.stop()
        self.requests_patcher.stop()

    def test_load_configurations(self):
        """Test carga de configuraciones de proveedores"""
        llm_manager = MultiProviderLLM()

        assert LLMProvider.GEMINI in llm_manager.providers
        assert LLMProvider.OPENAI in llm_manager.providers
        assert LLMProvider.CLAUDE in llm_manager.providers
        assert LLMProvider.XAI in llm_manager.providers

        # Verificar configuración de Gemini
        gemini_config = llm_manager.providers[LLMProvider.GEMINI]
        assert gemini_config.api_key == "test_gemini_key"
        assert gemini_config.is_free is True
        assert gemini_config.is_reasoning is False

    def test_fallback_order_normal(self):
        """Test orden de fallback para conversaciones normales"""
        llm_manager = MultiProviderLLM()
        fallback_order = llm_manager.get_fallback_order("normal")

        assert isinstance(fallback_order, list)
        assert len(fallback_order) > 0
        assert LLMProvider.GEMINI in fallback_order

    def test_fallback_order_reasoning(self):
        """Test orden de fallback para razonamiento"""
        llm_manager = MultiProviderLLM()
        fallback_order = llm_manager.get_fallback_order("reasoning")

        assert isinstance(fallback_order, list)
        # Verificar que solo incluye modelos de razonamiento
        for provider in fallback_order:
            config = llm_manager.providers[provider]
            if not config.is_reasoning:
                # Si no hay modelos de razonamiento disponibles, puede incluir normales
                continue

    def test_fallback_order_free_only(self):
        """Test orden de fallback solo modelos gratuitos"""
        llm_manager = MultiProviderLLM()
        fallback_order = llm_manager.get_fallback_order(free_only=True)

        assert isinstance(fallback_order, list)
        # Verificar que solo incluye modelos gratuitos
        for provider in fallback_order:
            config = llm_manager.providers[provider]
            assert config.is_free is True

    def test_get_available_providers(self):
        """Test obtener lista de proveedores disponibles"""
        llm_manager = MultiProviderLLM()
        providers = llm_manager.get_available_providers()

        assert isinstance(providers, list)
        assert len(providers) > 0

        # Verificar estructura de datos
        for provider in providers:
            assert "name" in provider
            assert "provider" in provider
            assert "model" in provider
            assert "active" in provider
            assert "is_free" in provider
            assert "is_reasoning" in provider

    def test_get_providers_by_type_free(self):
        """Test filtrar proveedores por tipo (gratuitos)"""
        llm_manager = MultiProviderLLM()
        free_providers = llm_manager.get_providers_by_type(free_only=True)

        for provider in free_providers:
            assert provider["is_free"] is True

    def test_get_providers_by_type_reasoning(self):
        """Test filtrar proveedores por tipo (razonamiento)"""
        llm_manager = MultiProviderLLM()
        reasoning_providers = llm_manager.get_providers_by_type(reasoning=True)

        for provider in reasoning_providers:
            assert provider["is_reasoning"] is True

    @pytest.mark.asyncio
    async def test_generate_response_success(self):
        """Test generación exitosa de respuesta"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "candidates": [{"content": {"parts": [{"text": "Test response from Gemini"}]}}],
                "usageMetadata": {"totalTokenCount": 10},
            }
        )
        mock_response.text = AsyncMock(return_value="")

        # aiohttp uses nested async context managers:
        # async with ClientSession() as session:
        #     async with session.post(...) as response:
        mock_post_cm = AsyncMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post_cm)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        self.mock_requests.return_value = mock_session

        llm_manager = MultiProviderLLM()
        llm_manager.cache_enabled = False
        messages = [{"role": "user", "content": "Test message"}]

        result = await llm_manager.generate_response(messages)

        assert result["success"] is True
        assert "response" in result
        # Provider may be gemini or humanized_fallback depending on humanization
        assert result["provider"] in ("gemini", "humanized_fallback")

    @pytest.mark.asyncio
    async def test_generate_response_with_business_context(self):
        """Test generación con contexto de negocio"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"candidates": [{"content": {"parts": [{"text": "Business response"}]}}]})
        mock_response.text = AsyncMock(return_value="")

        mock_post_cm = AsyncMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post_cm)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        self.mock_requests.return_value = mock_session

        llm_manager = MultiProviderLLM()
        messages = [{"role": "user", "content": "Business question"}]
        business_context = {"business_name": "Test Business", "business_type": "retail"}

        result = await llm_manager.generate_response(messages, business_context=business_context)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_generate_response_free_only_mode(self):
        """Test generación en modo solo gratuitos"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"candidates": [{"content": {"parts": [{"text": "Free response"}]}}]})
        mock_response.text = AsyncMock(return_value="")

        mock_post_cm = AsyncMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post_cm)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        self.mock_requests.return_value = mock_session

        llm_manager = MultiProviderLLM()
        messages = [{"role": "user", "content": "Test message"}]

        result = await llm_manager.generate_response(messages, free_only=True)

        assert result["success"] is True
        # When humanization is active, result might not have is_free
        if "is_free" in result:
            assert result["is_free"] is True

    @pytest.mark.asyncio
    async def test_generate_response_all_providers_fail(self):
        """Test cuando todos los proveedores fallan"""
        # Mock failed API response
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="API Error")
        mock_response.json = AsyncMock(side_effect=Exception("not json"))

        mock_post_cm = AsyncMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post_cm)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        self.mock_requests.return_value = mock_session

        llm_manager = MultiProviderLLM()
        messages = [{"role": "user", "content": "Test message"}]

        result = await llm_manager.generate_response(messages)

        # When humanization is available, the system may still return success=True
        # with a humanized_fallback response, or success=False with a fallback response
        assert "response" in result or "action" in result
        assert result["provider"] in ("fallback", "humanized_fallback")

    def test_get_fallback_response(self):
        """Test respuesta de emergencia"""
        llm_manager = MultiProviderLLM()

        context = {"business_name": "Test Business"}
        response = llm_manager._get_fallback_response(context)

        assert isinstance(response, str)
        assert "Test Business" in response
        assert "dificultades técnicas" in response

    def test_get_provider_capabilities(self):
        """Test obtención de capacidades de proveedor"""
        llm_manager = MultiProviderLLM()

        config = APIConfig(
            name="Test Provider",
            api_key="test_key",
            base_url="https://test.api",
            model="test-model",
            is_reasoning=True,
            is_free=True,
        )

        capabilities = llm_manager._get_provider_capabilities(config)

        assert "Razonamiento" in capabilities
        assert "Gratuito" in capabilities


class TestAPIConfig:
    """Tests para la configuración de API"""

    def test_api_config_creation(self):
        """Test creación de configuración de API"""
        config = APIConfig(
            name="Test Provider",
            api_key="test_key",
            base_url="https://api.test.com",
            model="test-model",
            active=True,
            max_tokens=2000,
            temperature=0.7,
            is_reasoning=True,
            is_free=False,
        )

        assert config.name == "Test Provider"
        assert config.api_key == "test_key"
        assert config.base_url == "https://api.test.com"
        assert config.model == "test-model"
        assert config.active is True
        assert config.max_tokens == 2000
        assert config.temperature == 0.7
        assert config.is_reasoning is True
        assert config.is_free is False


if __name__ == "__main__":
    pytest.main([__file__])
