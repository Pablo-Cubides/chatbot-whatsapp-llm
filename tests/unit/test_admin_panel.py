import sys
import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock, mock_open
from fastapi.testclient import TestClient
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from admin_panel import app, verify_token, ensure_bot_disabled_by_default


class TestAdminPanel:
    """Comprehensive tests for admin_panel.py FastAPI application"""

    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.client = TestClient(app)

        # Create test data directory structure
        self.data_dir = os.path.join(self.temp_dir, 'data')
        self.web_ui_dir = os.path.join(self.temp_dir, 'web_ui')
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.web_ui_dir, exist_ok=True)

        # Create test settings file
        self.settings_file = os.path.join(self.data_dir, 'settings.json')
        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump({"respond_to_all": False, "test_mode": True}, f)

        # Create test UI file
        self.index_file = os.path.join(self.web_ui_dir, 'index.html')
        with open(self.index_file, 'w', encoding='utf-8') as f:
            f.write('<html><body>Test UI</body></html>')

        # Mock environment
        self.env_patcher = patch.dict(os.environ, {
            "ADMIN_TOKEN": "testtoken123"
        })
        self.env_patcher.start()

    def teardown_method(self):
        """Clean up test environment"""
        self.env_patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_app_initialization(self):
        """Test FastAPI app initialization"""
        assert app.title == "Chatbot Admin Panel"
        assert len(app.routes) > 10  # Should have many routes

    def test_verify_token_valid(self):
        """Test token verification with valid token"""
        result = verify_token("Bearer admintoken")
        assert result == "admin"

    def test_verify_token_invalid(self):
        """Test token verification with invalid token"""
        with pytest.raises(Exception):  # Should raise HTTPException
            verify_token("Bearer invalidtoken")

    def test_verify_token_missing(self):
        """Test token verification with missing token"""
        with pytest.raises(Exception):  # Should raise HTTPException
            verify_token("")

    @patch('admin_panel.initialize_schema')
    def test_ensure_bot_disabled_by_default(self, mock_init):
        """Test bot is disabled by default on startup"""
        # Reset settings file
        if os.path.exists(self.settings_file):
            os.remove(self.settings_file)

        with patch('admin_panel.os.path.dirname', return_value=self.temp_dir):
            ensure_bot_disabled_by_default()

        # Check settings were created with respond_to_all = False
        assert os.path.exists(self.settings_file)
        with open(self.settings_file, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            assert settings['respond_to_all'] is False

    def test_root_endpoint(self):
        """Test root endpoint returns status info"""
        response = self.client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data

    def test_healthz_endpoint(self):
        """Test health check endpoint"""
        response = self.client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    @patch('admin_panel.get_session')
    def test_models_list_unauthorized(self, mock_session):
        """Test models list requires authentication"""
        response = self.client.get("/models")
        assert response.status_code == 401

    @patch('admin_panel.get_session')
    def test_models_list_authorized(self, mock_session):
        """Test models list with valid authentication"""
        # Mock database session
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.query.return_value.filter.return_value.all.return_value = []

        response = self.client.get("/models", headers={"Authorization": "Bearer admintoken"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @patch('admin_panel.get_session')
    def test_create_model(self, mock_session):
        """Test model creation"""
        # Mock database session
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_model = MagicMock()
        mock_model.id = 1
        mock_model.name = "Test Model"
        mock_session_instance.add.return_value = None
        mock_session_instance.commit.return_value = None
        mock_session_instance.refresh.return_value = None

        model_data = {
            "name": "Test Model",
            "provider": "test_provider",
            "model_type": "local"
        }

        response = self.client.post(
            "/models",
            json=model_data,
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    @patch('admin_panel.get_session')
    def test_create_rule(self, mock_session):
        """Test rule creation"""
        # Mock database session
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_rule = MagicMock()
        mock_rule.id = 1
        mock_session_instance.add.return_value = None
        mock_session_instance.commit.return_value = None
        mock_session_instance.refresh.return_value = None

        rule_data = {
            "name": "Test Rule",
            "every_n_messages": 5,
            "model_id": 1,
            "enabled": True
        }

        response = self.client.post(
            "/rules",
            json=rule_data,
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    @patch('admin_panel.get_session')
    def test_add_contact(self, mock_session):
        """Test contact addition"""
        # Mock database session
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_contact = MagicMock()
        mock_contact.chat_id = "123456789"
        mock_session_instance.query.return_value.filter.return_value.first.return_value = None

        contact_data = {
            "contact_id": "123456789",
            "label": "Test Contact"
        }

        response = self.client.post(
            "/contacts",
            json=contact_data,
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200

    @patch('admin_panel.os.path.exists')
    @patch('builtins.open', new_callable=MagicMock)
    def test_dashboard_endpoint(self, mock_open, mock_exists):
        """Test dashboard HTML endpoint"""
        mock_exists.return_value = True
        mock_file = MagicMock()
        mock_file.read.return_value = "<html>Dashboard</html>"
        mock_open.return_value.__enter__.return_value = mock_file

        response = self.client.get("/dashboard")
        assert response.status_code == 200
        assert "html" in response.text.lower()

    @patch('admin_panel.subprocess.run')
    def test_lmstudio_health_check(self, mock_subprocess):
        """Test LM Studio health check"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "LM Studio is running"
        mock_subprocess.return_value = mock_result

        response = self.client.get(
            "/api/lmstudio/health",
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200

    @patch('admin_panel.requests.get')
    def test_lmstudio_models_endpoint(self, mock_requests):
        """Test LM Studio models listing"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"id": "model1"}, {"id": "model2"}]}
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response

        response = self.client.get(
            "/api/lmstudio/models",
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "main_models" in data
        assert "reasoning_models" in data

    @patch('admin_panel.subprocess.run')
    def test_lmstudio_start_server(self, mock_subprocess):
        """Test LM Studio server start"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        response = self.client.post(
            "/api/lmstudio/server/start",
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200

    @patch('admin_panel._kill_processes')
    @patch('admin_panel._kill_processes_except_current')
    @patch('admin_panel._kill_processes')
    def test_system_stop_all(self, mock_kill_browser, mock_kill_except, mock_kill_name):
        """Test system stop all processes"""
        mock_kill_name.return_value = [123, 456]
        mock_kill_except.return_value = [789]
        mock_kill_browser.return_value = [101]

        response = self.client.post(
            "/api/system/stop-all",
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "total_killed_pids" in data

    @patch('admin_panel.get_session')
    def test_get_chats_list(self, mock_session):
        """Test getting list of chats"""
        # Mock database session
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.query.return_value.all.return_value = []

        response = self.client.get(
            "/api/chats",
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "chats" in data
        assert isinstance(data["chats"], list)

    @patch('admin_panel.chat_sessions.load_last_context')
    def test_get_chat_details(self, mock_load_context):
        """Test getting specific chat details"""
        mock_load_context.return_value = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]

        response = self.client.get(
            "/api/chats/test_chat_123",
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "chat_id" in data
        assert "files" in data
        assert "contexto" in data["files"]

    @patch('admin_panel.update_chat_context_and_profile')
    def test_refresh_chat_context(self, mock_update):
        """Test chat context refresh"""
        mock_update.return_value = {
            "version": 1,
            "wrote_contexto": True,
            "wrote_perfil": True
        }

        response = self.client.post(
            "/api/chats/test_chat_123/refresh-context",
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "version" in data

    def test_get_status(self):
        """Test status endpoint"""
        response = self.client.get(
            "/api/status",
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    @patch('admin_panel.json.dump')
    def test_update_settings(self, mock_json_dump):
        """Test settings update"""
        settings_data = {
            "respond_to_all": True,
            "test_mode": False
        }

        response = self.client.put(
            "/api/settings",
            json=settings_data,
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200

    @patch('builtins.open', new_callable=mock_open, read_data='{"temperature": 0.8, "max_tokens": 1024}')
    @patch('os.path.exists')
    def test_get_settings(self, mock_exists, mock_file):
        """Test settings retrieval"""
        mock_exists.return_value = True

        response = self.client.get(
            "/api/settings",
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "temperature" in data

    @patch('admin_panel.get_session')
    def test_add_allowed_contact(self, mock_session):
        """Test adding allowed contact"""
        # Mock database session
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        contact_data = {
            "chat_id": "123456789",
            "initial_context": "Test context",
            "objective": "Test objective"
        }

        response = self.client.post(
            "/api/allowed-contacts",
            json=contact_data,
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200

    @patch('admin_panel.get_session')
    def test_get_allowed_contacts(self, mock_session):
        """Test getting allowed contacts list"""
        # Mock database session
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.query.return_value.all.return_value = []

        response = self.client.get(
            "/api/allowed-contacts",
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @patch('admin_panel.get_session')
    def test_delete_allowed_contact(self, mock_session):
        """Test deleting allowed contact"""
        # Mock database session
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_contact = MagicMock()
        mock_session_instance.query.return_value.filter.return_value.first.return_value = mock_contact

        response = self.client.delete(
            "/api/allowed-contacts/123456789",
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200

    @patch('admin_panel.json.load')
    @patch('admin_panel.json.dump')
    def test_toggle_chat_setting(self, mock_json_dump, mock_json_load):
        """Test toggling chat settings"""
        mock_json_load.return_value = {"respond_to_all": False}

        response = self.client.post(
            "/api/settings/chat/toggle",
            json={"setting": "respond_to_all"},
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200

    @patch('admin_panel.get_session')
    def test_clear_conversations(self, mock_session):
        """Test clearing conversations for a chat"""
        # Mock database session
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        response = self.client.post(
            "/api/conversations/clear",
            json={"chat_id": "test_chat_123"},
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200

    @patch('admin_panel.get_session')
    def test_clear_all_conversations(self, mock_session):
        """Test clearing all conversations"""
        # Mock database session
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        response = self.client.post(
            "/api/conversations/clear-all",
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200

    @patch('admin_panel.stub_chat.chat')
    def test_chat_compose(self, mock_generate):
        """Test chat message composition"""
        mock_generate.return_value = "Test response"

        chat_data = {
            "chat_id": "test_chat_123",
            "objective": "Test objective",
            "additional_context": "Test context"
        }

        response = self.client.post(
            "/api/chat/compose",
            json=chat_data,
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "reply" in data

    @patch('admin_panel.os.makedirs')
    @patch('builtins.open', new_callable=MagicMock)
    def test_file_upload(self, mock_open, mock_makedirs):
        """Test file upload functionality"""
        # Mock file operations
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        # Create test file data
        file_content = b"test file content"
        files = {"file": ("test.txt", file_content, "text/plain")}

        response = self.client.post(
            "/api/media/upload",
            files=files,
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200

    @patch('admin_panel.get_session')
    def test_get_analytics(self, mock_session):
        """Test analytics endpoint"""
        # Mock database session
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.execute.return_value.fetchall.return_value = []

        response = self.client.get(
            "/api/analytics",
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    @patch('admin_panel.get_session')
    def test_models_online_list(self, mock_session):
        """Test online models listing"""
        # Mock database session
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.query.return_value.filter.return_value.all.return_value = []

        response = self.client.get(
            "/api/models/online",
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @patch('admin_panel.get_session')
    def test_models_local_list(self, mock_session):
        """Test local models listing"""
        # Mock database session
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.query.return_value.filter.return_value.all.return_value = []

        response = self.client.get(
            "/api/models/local",
            headers={"Authorization": "Bearer admintoken"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
