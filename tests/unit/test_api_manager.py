import sys
import os
import tempfile
import shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestAPIManager:
    """Test suite for APIManager functionality"""

    def setup_method(self):
        """Set up test environment with temporary directory"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_api_manager_initialization(self):
        """Test APIManager initialization"""
        from api_manager import APIManager

        manager = APIManager(self.temp_dir)
        assert manager.data_dir == self.temp_dir
        assert manager.api_providers is not None
        assert 'openai' in manager.api_providers
        assert 'anthropic' in manager.api_providers
        assert 'google' in manager.api_providers

    def test_get_provider_info(self):
        """Test getting provider information"""
        from api_manager import APIManager

        manager = APIManager(self.temp_dir)
        info = manager.get_provider_info('openai')

        assert info is not None
        assert info['name'] == 'OpenAI'
        assert 'base_url' in info
        assert 'key_format' in info

    def test_get_provider_info_unknown(self):
        """Test getting info for unknown provider returns None"""
        from api_manager import APIManager

        manager = APIManager(self.temp_dir)
        info = manager.get_provider_info('unknown_provider')

        assert info is None

    def test_list_configured_apis_empty(self):
        """Test listing configured APIs when none are configured"""
        from api_manager import APIManager

        manager = APIManager(self.temp_dir)
        apis = manager.list_configured_apis()

        assert isinstance(apis, dict)
        # Should have providers but no configured keys initially
        assert len(apis) >= 4  # At least openai, anthropic, google, xai

    def test_store_and_get_api_key(self):
        """Test storing and retrieving API key"""
        from api_manager import APIManager

        manager = APIManager(self.temp_dir)
        test_key = "sk-test123456789"

        # Store API key
        success = manager.store_api_key('openai', test_key)
        assert success is True

        # Retrieve API key
        retrieved_key = manager.get_api_key('openai')
        assert retrieved_key == test_key

    def test_get_api_key_not_configured(self):
        """Test getting API key when not configured"""
        from api_manager import APIManager

        manager = APIManager(self.temp_dir)
        key = manager.get_api_key('openai')

        assert key is None

    def test_remove_api_key(self):
        """Test removing API key"""
        from api_manager import APIManager

        manager = APIManager(self.temp_dir)
        test_key = "sk-test123456789"

        # Store and verify
        manager.store_api_key('openai', test_key)
        assert manager.get_api_key('openai') == test_key

        # Remove and verify
        success = manager.remove_api_key('openai')
        assert success is True
        assert manager.get_api_key('openai') is None

    def test_store_api_key_invalid_provider(self):
        """Test storing API key for invalid provider raises error"""
        from api_manager import APIManager

        manager = APIManager(self.temp_dir)

        try:
            manager.store_api_key('invalid_provider', 'test_key')
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Proveedor no soportado" in str(e)

    def test_test_api_connection_no_key(self):
        """Test API connection test when no key is configured"""
        from api_manager import APIManager

        manager = APIManager(self.temp_dir)
        result = manager.test_api_connection('openai')

        assert result['success'] is False
        assert 'No API key configured' in result['error']

    def test_test_api_connection_with_key(self):
        """Test API connection test when key is configured"""
        from api_manager import APIManager

        manager = APIManager(self.temp_dir)
        test_key = "sk-test123456789"

        # Configure key
        manager.store_api_key('openai', test_key)

        # Test connection
        result = manager.test_api_connection('openai')

        assert result['success'] is True
        assert 'OpenAI' in result['message']

    def test_update_api_metadata(self):
        """Test updating API metadata"""
        from api_manager import APIManager

        manager = APIManager(self.temp_dir)

        # Store key with metadata
        manager.store_api_key('openai', 'sk-test123', {'test': 'value'})

        # Update metadata
        success = manager.update_api_metadata('openai', {'updated': 'yes'})
        assert success is True
