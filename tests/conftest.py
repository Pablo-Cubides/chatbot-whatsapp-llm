"""
Test configuration and fixtures for WhatsApp LLM Chatbot
"""
import pytest
import json
import tempfile
import shutil
from unittest.mock import Mock
from pathlib import Path

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "test_data"
TEST_DATA_DIR.mkdir(exist_ok=True)

@pytest.fixture
def mock_page():
    """Mock Playwright page object"""
    page = Mock()
    page.locator.return_value = Mock()
    page.locator.return_value.count.return_value = 1
    page.locator.return_value.first = Mock()
    page.locator.return_value.inner_text.return_value = "Test message"
    page.wait_for_timeout = Mock()
    page.wait_for_selector = Mock()
    page.click = Mock()
    page.goto = Mock()
    return page

@pytest.fixture
def sample_chat_history():
    """Sample conversation history for testing"""
    return [
        {"role": "user", "content": "Hola, ¿cómo estás?"},
        {"role": "assistant", "content": "¡Hola! Estoy muy bien, gracias por preguntar. ¿Cómo puedo ayudarte hoy?"},
        {"role": "user", "content": "¿Puedes ayudarme con información sobre productos?"}
    ]

@pytest.fixture
def sample_manual_queue():
    """Sample manual message queue for testing"""
    return [
        {
            "id": "manual_1694901234",
            "chat_id": "+573107601252",
            "message": "Hola, este es un mensaje de prueba",
            "timestamp": "2025-09-16T10:30:00",
            "status": "pending"
        },
        {
            "id": "manual_1694901235",
            "chat_id": "+573107601253",
            "message": "Otro mensaje de prueba",
            "timestamp": "2025-09-16T10:31:00",
            "status": "sent"
        }
    ]

@pytest.fixture
def temp_dir():
    """Temporary directory for test files"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing"""
    test_env = {
        "LM_STUDIO_BASE_URL": "http://localhost:1234",
        "OPENAI_API_KEY": "test-key-123",
        "LOG_LEVEL": "DEBUG",
        "AUTOMATION_ACTIVE": "true",
        "TYPING_PER_CHAR": "0.01"
    }
    
    for key, value in test_env.items():
        monkeypatch.setenv(key, value)
    
    return test_env

@pytest.fixture
def mock_lm_studio_response():
    """Mock LM Studio API response"""
    return {
        "choices": [
            {
                "message": {
                    "content": "Esta es una respuesta de prueba del modelo LLM"
                }
            }
        ]
    }

@pytest.fixture
def sample_whatsapp_elements():
    """Sample WhatsApp DOM elements for testing"""
    return {
        "chat_list": "div[role='listitem']",
        "message_input": "div[data-testid='conversation-compose-box-input']",
        "search_box": "div[data-testid='chat-list-search']",
        "unread_badge": "span[data-testid='unread-badge']"
    }

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment before each test"""
    # Ensure test data directory exists
    TEST_DATA_DIR.mkdir(exist_ok=True)
    
    # Create test config file
    test_config = {
        "whatsappUrl": "https://web.whatsapp.com",
        "headless": True,
        "messageCheckInterval": 1,
        "maxRetries": 2,
        "navigationTimeout": 5000,
        "userDataDir": str(TEST_DATA_DIR / "test_profile")
    }
    
    config_file = TEST_DATA_DIR / "test_config.json"
    with open(config_file, 'w') as f:
        json.dump(test_config, f)
    
    yield
    
    # Cleanup after test
    if config_file.exists():
        config_file.unlink()

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing"""
    client = Mock()
    client.chat.completions.create.return_value = Mock(
        choices=[
            Mock(message=Mock(content="Test response from OpenAI"))
        ]
    )
    return client