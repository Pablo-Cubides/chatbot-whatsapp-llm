import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from requests.exceptions import RequestException, Timeout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from openai_integration import OpenAIIntegration
from claude_integration import ClaudeIntegration
from gemini_integration import GeminiIntegration
from xai_integration import XAIIntegration
from ollama_integration import OllamaIntegration


class TestIntegrations:
    """Comprehensive tests for all integration modules"""

    def setup_method(self):
        """Setup before each test"""
        self.mock_api_manager = MagicMock()

    # OpenAI Integration Tests
    def test_openai_init(self):
        """Test OpenAI integration initialization"""
        integration = OpenAIIntegration(self.mock_api_manager)
        assert integration.api_manager == self.mock_api_manager
        assert integration.provider == 'openai'
        assert integration.base_url == 'https://api.openai.com/v1'
        assert 'gpt-4' in integration.available_models

    @patch('openai_integration.requests.get')
    def test_openai_get_api_key_success(self, mock_get):
        """Test OpenAI API key retrieval success"""
        self.mock_api_manager.get_api_key.return_value = 'test-key-123'

        integration = OpenAIIntegration(self.mock_api_manager)
        result = integration._get_api_key()

        assert result == 'test-key-123'
        self.mock_api_manager.get_api_key.assert_called_once_with('openai', decrypt=True)

    @patch('openai_integration.requests.get')
    def test_openai_get_api_key_none(self, mock_get):
        """Test OpenAI API key retrieval when none available"""
        self.mock_api_manager.get_api_key.return_value = None

        integration = OpenAIIntegration(self.mock_api_manager)
        result = integration._get_api_key()

        assert result is None

    @patch('openai_integration.requests.post')
    def test_openai_make_request_success(self, mock_post):
        """Test OpenAI request making success"""
        mock_response = MagicMock()
        mock_response.json.return_value = {'data': 'test'}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        integration = OpenAIIntegration(self.mock_api_manager)
        with patch.object(integration, '_get_api_key', return_value='test-key'):
            result = integration._make_request('chat/completions', 'POST', {'test': 'data'})

        assert result == {'data': 'test'}
        mock_post.assert_called_once()

    @patch('openai_integration.requests.post')
    def test_openai_make_request_error(self, mock_post):
        """Test OpenAI request making with error"""
        mock_post.side_effect = RequestException("Connection failed")

        integration = OpenAIIntegration(self.mock_api_manager)
        with patch.object(integration, '_get_api_key', return_value='test-key'):
            with pytest.raises(Exception) as exc_info:
                integration._make_request('chat/completions', 'POST', {'test': 'data'})

        assert 'Connection failed' in str(exc_info.value)

    @patch('openai_integration.requests.get')
    def test_openai_test_connection_success(self, mock_get):
        """Test OpenAI connection test success"""
        mock_response = MagicMock()
        mock_response.json.return_value = {'data': [{'id': 'gpt-3.5-turbo'}]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        integration = OpenAIIntegration(self.mock_api_manager)
        with patch.object(integration, '_get_api_key', return_value='test-key'):
            result = integration.test_connection()

        assert result['success']
        assert 'Connected successfully' in result['message']

    @patch('openai_integration.requests.get')
    def test_openai_test_connection_no_key(self, mock_get):
        """Test OpenAI connection test without API key"""
        integration = OpenAIIntegration(self.mock_api_manager)
        with patch.object(integration, '_get_api_key', return_value=None):
            result = integration.test_connection()

        assert not result['success']
        assert 'No OpenAI API key configured' in result['message']

    def test_openai_get_available_models(self):
        """Test OpenAI available models retrieval"""
        integration = OpenAIIntegration(self.mock_api_manager)
        
        # Mock the _make_request method to return successful API response
        mock_response = {
            'data': [
                {'id': 'gpt-4', 'object': 'model'},
                {'id': 'gpt-3.5-turbo', 'object': 'model'}
            ]
        }
        
        with patch.object(integration, '_make_request', return_value=mock_response):
            result = integration.get_available_models()
        
        assert result['success']
        assert 'models' in result
        assert len(result['models']) > 0

    @patch('openai_integration.requests.post')
    def test_openai_generate_response_success(self, mock_post):
        """Test OpenAI response generation success"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Test response'}, 'finish_reason': 'stop'}],
            'usage': {'total_tokens': 100, 'prompt_tokens': 50, 'completion_tokens': 50}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        integration = OpenAIIntegration(self.mock_api_manager)
        messages = [{'role': 'user', 'content': 'Hello'}]

        with patch.object(integration, '_get_api_key', return_value='test-key'):
            result = integration.generate_response(messages, 'gpt-3.5-turbo')

        assert result['success']
        assert result['content'] == 'Test response'
        assert result['usage']['total_tokens'] == 100

    def test_openai_estimate_cost(self):
        """Test OpenAI cost estimation"""
        integration = OpenAIIntegration(self.mock_api_manager)
        result = integration.estimate_cost("Hello world", 'gpt-3.5-turbo')

        assert 'success' in result
        assert 'estimated_cost_usd' in result
        assert 'estimated_tokens' in result

    # Claude Integration Tests
    def test_claude_init(self):
        """Test Claude integration initialization"""
        integration = ClaudeIntegration(self.mock_api_manager)
        assert integration.api_manager == self.mock_api_manager
        assert integration.provider == 'anthropic'
        assert integration.base_url == 'https://api.anthropic.com/v1'
        assert 'claude-3-haiku-20240307' in integration.available_models

    @patch('claude_integration.requests.post')
    def test_claude_test_connection_success(self, mock_post):
        """Test Claude connection test success"""
        mock_response = MagicMock()
        mock_response.json.return_value = {'type': 'message', 'content': [{'text': 'OK'}]}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        integration = ClaudeIntegration(self.mock_api_manager)
        with patch.object(integration, '_get_api_key', return_value='test-key'):
            result = integration.test_connection()

        assert result['success']
        assert 'Connected successfully' in result['message']

    @patch('claude_integration.requests.post')
    def test_claude_generate_response_success(self, mock_post):
        """Test Claude response generation success"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'content': [{'text': 'Test Claude response'}],
            'usage': {'input_tokens': 10, 'output_tokens': 20}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        integration = ClaudeIntegration(self.mock_api_manager)
        messages = [{'role': 'user', 'content': 'Hello'}]

        with patch.object(integration, '_get_api_key', return_value='test-key'):
            result = integration.generate_response(messages, 'claude-3-haiku-20240307')

        assert result['success']
        assert result['content'] == 'Test Claude response'
        assert result['usage']['input_tokens'] == 10

    def test_claude_format_messages(self):
        """Test Claude message formatting"""
        integration = ClaudeIntegration(self.mock_api_manager)
        messages = [
            {'role': 'system', 'content': 'You are helpful'},
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi there'}
        ]

        result = integration._format_messages_for_claude(messages)

        # Claude converts system messages to user messages with "System:" prefix
        assert len(result) == 3
        assert result[0]['role'] == 'user'
        assert 'System: You are helpful' in result[0]['content']
        assert result[1]['role'] == 'user'
        assert result[1]['content'] == 'Hello'
        assert result[2]['role'] == 'assistant'

    # Gemini Integration Tests
    def test_gemini_init(self):
        """Test Gemini integration initialization"""
        integration = GeminiIntegration(self.mock_api_manager)
        assert integration.api_manager == self.mock_api_manager
        assert integration.provider == 'google'
        assert integration.base_url == 'https://generativelanguage.googleapis.com/v1beta'
        assert 'gemini-1.5-flash' in integration.available_models

    @patch('gemini_integration.requests.post')
    def test_gemini_generate_response_success(self, mock_post):
        """Test Gemini response generation success"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'candidates': [{
                'content': {'parts': [{'text': 'Test Gemini response'}]},
                'finishReason': 'STOP'
            }],
            'usageMetadata': {'totalTokenCount': 50}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        integration = GeminiIntegration(self.mock_api_manager)
        messages = [{'role': 'user', 'content': 'Hello'}]

        with patch.object(integration, '_get_api_key', return_value='test-key'):
            result = integration.generate_response(messages, 'gemini-1.5-flash')

        assert result['success']
        assert result['content'] == 'Test Gemini response'
        assert result['usage']['total_tokens'] == 50

    def test_gemini_format_messages(self):
        """Test Gemini message formatting"""
        integration = GeminiIntegration(self.mock_api_manager)
        messages = [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi there'}
        ]

        result = integration._format_messages_for_gemini(messages, 'gemini-1.5-flash')

        assert 'contents' in result
        assert len(result['contents']) == 2

    # XAI Integration Tests
    def test_xai_init(self):
        """Test XAI integration initialization"""
        integration = XAIIntegration(self.mock_api_manager)
        assert integration.api_manager == self.mock_api_manager
        assert integration.provider == 'xai'
        assert integration.base_url == 'https://api.x.ai/v1'
        assert 'grok-beta' in integration.available_models

    @patch('xai_integration.requests.post')
    def test_xai_generate_response_success(self, mock_post):
        """Test XAI response generation success"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Test XAI response'}}],
            'usage': {'total_tokens': 75}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        integration = XAIIntegration(self.mock_api_manager)
        messages = [{'role': 'user', 'content': 'Hello'}]

        with patch.object(integration, '_get_api_key', return_value='test-key'):
            result = integration.generate_response(messages, 'grok-beta')

        assert result['success']
        assert result['content'] == 'Test XAI response'
        assert result['usage']['total_tokens'] == 75

    def test_xai_format_messages(self):
        """Test XAI message formatting"""
        integration = XAIIntegration(self.mock_api_manager)
        messages = [
            {'role': 'system', 'content': 'You are helpful'},
            {'role': 'user', 'content': 'Hello'}
        ]

        result = integration._format_messages_for_xai(messages)

        assert len(result) == 2
        assert result[0]['role'] == 'system'
        assert result[1]['role'] == 'user'

    def test_xai_get_rate_limit_info(self):
        """Test XAI rate limit info"""
        integration = XAIIntegration(self.mock_api_manager)
        result = integration.get_rate_limit_info()

        assert result['success']
        assert 'rate_limits' in result
        assert 'recommendations' in result

    # Ollama Integration Tests
    def test_ollama_init(self):
        """Test Ollama integration initialization"""
        integration = OllamaIntegration(self.mock_api_manager)
        assert integration.api_manager == self.mock_api_manager
        assert integration.provider == 'ollama'
        assert 'http://localhost:11434' in integration.alternative_urls

    @patch('ollama_integration.requests.get')
    def test_ollama_get_working_url_success(self, mock_get):
        """Test Ollama working URL detection success"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        integration = OllamaIntegration(self.mock_api_manager)
        result = integration._get_working_url()

        assert result == 'http://localhost:11434'

    @patch('ollama_integration.requests.get')
    def test_ollama_get_working_url_none(self, mock_get):
        """Test Ollama working URL detection failure"""
        mock_get.side_effect = RequestException("Connection failed")

        integration = OllamaIntegration(self.mock_api_manager)
        result = integration._get_working_url()

        assert result is None

    @patch('ollama_integration.requests.get')
    def test_ollama_test_connection_success(self, mock_get):
        """Test Ollama connection test success"""
        # Mock for _get_working_url
        mock_url_response = MagicMock()
        mock_url_response.status_code = 200
        mock_get.return_value = mock_url_response

        # Mock for _make_request calls
        with patch.object(OllamaIntegration, '_make_request') as mock_make_request:
            mock_make_request.side_effect = [
                {'version': '1.0.0'},  # api/version
                {'models': [{'name': 'llama3.2'}]}  # api/tags
            ]

            integration = OllamaIntegration(self.mock_api_manager)
            result = integration.test_connection()

        assert result['success']
        assert 'Connected to Ollama' in result['message']

    @patch('ollama_integration.requests.get')
    def test_ollama_get_available_models_success(self, mock_get):
        """Test Ollama available models retrieval success"""
        # Mock for _get_working_url
        mock_url_response = MagicMock()
        mock_url_response.status_code = 200
        mock_get.return_value = mock_url_response

        # Mock for _make_request
        with patch.object(OllamaIntegration, '_make_request') as mock_make_request:
            mock_make_request.return_value = {
                'models': [
                    {'name': 'llama3.2', 'size': 1000000},
                    {'name': 'mistral', 'size': 2000000}
                ]
            }

            integration = OllamaIntegration(self.mock_api_manager)
            result = integration.get_available_models()

        assert result['success']
        assert len(result['models']) == 2
        assert 'llama3.2' in result['models']

    @patch('ollama_integration.requests.post')
    def test_ollama_generate_response_success(self, mock_post):
        """Test Ollama response generation success"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'response': 'Test Ollama response',
            'done': True,
            'eval_count': 25,
            'prompt_eval_count': 5
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Mock _get_working_url and get_available_models
        with patch.object(OllamaIntegration, '_get_working_url', return_value='http://localhost:11434'), \
             patch.object(OllamaIntegration, 'get_available_models', return_value={'success': True, 'models': {'llama3.2': {}}}):
            integration = OllamaIntegration(self.mock_api_manager)
            messages = [{'role': 'user', 'content': 'Hello'}]

            result = integration.generate_response(messages, 'llama3.2')

        assert result['success']
        assert result['content'] == 'Test Ollama response'
        assert result['usage']['total_tokens'] == 30  # 5 + 25

    def test_ollama_format_messages(self):
        """Test Ollama message formatting"""
        integration = OllamaIntegration(self.mock_api_manager)
        messages = [
            {'role': 'system', 'content': 'You are helpful'},
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi there'}
        ]

        result = integration._format_messages_for_ollama(messages)

        assert isinstance(result, str)
        assert 'You are helpful' in result
        assert 'Hello' in result
        assert 'Hi there' in result

    @patch('ollama_integration.requests.post')
    def test_ollama_pull_model_success(self, mock_post):
        """Test Ollama model pulling success"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with patch.object(OllamaIntegration, '_get_working_url', return_value='http://localhost:11434'):
            integration = OllamaIntegration(self.mock_api_manager)
            result = integration.pull_model('llama3.2')

        assert result['success']

    @patch('ollama_integration.requests.delete')
    def test_ollama_delete_model_success(self, mock_delete):
        """Test Ollama model deletion success"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_delete.return_value = mock_response

        with patch.object(OllamaIntegration, '_make_request') as mock_make_request:
            mock_make_request.return_value = None  # DELETE request doesn't return data
            integration = OllamaIntegration(self.mock_api_manager)
            result = integration.delete_model('llama3.2')

        assert result['success']

    def test_ollama_estimate_cost(self):
        """Test Ollama cost estimation"""
        integration = OllamaIntegration(self.mock_api_manager)
        result = integration.estimate_cost("Hello world", 'llama3.2')

        assert result['success']
        assert result['estimated_cost_usd'] == 0.0
        assert 'local_model' in result

    # Cross-integration error handling tests
    @patch('openai_integration.requests.get')
    def test_openai_timeout_error(self, mock_get):
        """Test OpenAI timeout error handling"""
        mock_get.side_effect = Timeout("Request timed out")

        integration = OpenAIIntegration(self.mock_api_manager)
        with patch.object(integration, '_get_api_key', return_value='test-key'):
            with pytest.raises(Exception) as exc_info:
                integration._make_request('test-endpoint')

        assert 'Request timed out' in str(exc_info.value)

    @patch('claude_integration.requests.post')
    def test_claude_streaming_response(self, mock_post):
        """Test Claude streaming response generation"""
        # Mock streaming response with proper SSE format
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = [
            b'data: {"type": "content_block_delta", "delta": {"text": "Test"}}',
            b'data: {"type": "message_stop"}'
        ]
        mock_post.return_value = mock_response

        integration = ClaudeIntegration(self.mock_api_manager)
        messages = [{'role': 'user', 'content': 'Hello'}]

        with patch.object(integration, '_get_api_key', return_value='test-key'):
            results = list(integration.generate_streaming_response(messages, 'claude-3-haiku-20240307'))

        assert len(results) > 0
        assert any('Test' in result.get('content', '') for result in results)

    @patch('gemini_integration.requests.post')
    def test_gemini_streaming_response(self, mock_post):
        """Test Gemini streaming response generation"""
        # Mock streaming response
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = [
            b'data: {"candidates": [{"content": {"parts": [{"text": "Test"}]}}]}',
            b'data: {"candidates": [{"finishReason": "STOP"}]}'
        ]
        mock_post.return_value = mock_response

        integration = GeminiIntegration(self.mock_api_manager)
        messages = [{'role': 'user', 'content': 'Hello'}]

        with patch.object(integration, '_get_api_key', return_value='test-key'):
            results = list(integration.generate_streaming_response(messages, 'gemini-1.5-flash'))

        assert len(results) > 0
        assert any('Test' in result.get('content', '') for result in results)
