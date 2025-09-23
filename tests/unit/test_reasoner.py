import sys
import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

class TestReasoner:
    """Comprehensive tests for reasoner.py module"""

    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.chat_id = "test_chat_123"

        # Create test payload file
        self.payload_path = os.path.join(self.temp_dir, "payload_reasoner.json")
        self.test_payload = {
            "model": "test-model",
            "messages": [
                {"role": "system", "content": "You are a reasoning assistant."}
            ],
            "temperature": 0.7
        }
        with open(self.payload_path, 'w', encoding='utf-8') as f:
            json.dump(self.test_payload, f)

        # Mock environment
        self.env_patcher = patch.dict(os.environ, {
            "REASONER_PAYLOAD_PATH": self.payload_path
        })
        self.env_patcher.start()

    def teardown_method(self):
        """Clean up test environment"""
        self.env_patcher.stop()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


    def test_load_payload(self):
        """Test loading payload (newer version)"""
        from reasoner import _load_payload
        import shutil

        # Copy payload file to temp directory
        payload_src = os.path.join(os.path.dirname(__file__), "..", "..", "payload_reasoner.json")
        payload_dst = os.path.join(self.temp_dir, "payload_reasoner.json")
        shutil.copy2(payload_src, payload_dst)

        with patch.dict(os.environ, {"REASONER_PAYLOAD_PATH": payload_dst}):
            result = _load_payload()
            assert isinstance(result, dict)
            assert "model" in result
            assert "messages" in result

    @patch('reasoner.get_session')
    @patch('crypto.decrypt_text')
    @patch('reasoner.client')
    def test_last_turns_with_data(self, mock_client, mock_decrypt, mock_get_session):
        """Test fetching last turns from conversation history"""
        from reasoner import _last_turns

        # Mock database session and query
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        # Mock conversation rows
        mock_row1 = MagicMock()
        mock_row1.context = "encrypted_context_1"
        mock_row2 = MagicMock()
        mock_row2.context = "encrypted_context_2"

        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_row1, mock_row2]

        # Mock decryption results
        mock_decrypt.side_effect = [
            json.dumps([
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"}
            ]),
            json.dumps([
                {"role": "user", "content": "How are you?"},
                {"role": "assistant", "content": "I'm fine"}
            ])
        ]

        result = _last_turns(self.chat_id, n_turns=10)

        # Verify database calls
        mock_session.query.assert_called_once()
        mock_session.close.assert_called_once()

        # Verify result contains expected text
        assert "user: Hello" in result
        assert "assistant: Hi there" in result
        assert "user: How are you?" in result
        assert "assistant: I'm fine" in result

    @patch('reasoner.get_session')
    @patch('reasoner.client')
    def test_last_turns_empty_history(self, mock_client, mock_get_session):
        """Test fetching last turns when no history exists"""
        from reasoner import _last_turns

        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = _last_turns(self.chat_id)
        assert result == ""

    @patch('reasoner.get_profile')
    @patch('reasoner.get_active_strategy')
    @patch('reasoner.load_last_context')
    @patch('reasoner.client')
    def test_build_reasoner_messages(self, mock_client, mock_load_context, mock_get_strategy, mock_get_profile):
        """Test building reasoner messages"""
        from reasoner import _build_reasoner_messages

        # Mock profile
        mock_profile = MagicMock()
        mock_profile.objective = "Test objective"
        mock_profile.instructions = "Test instructions"
        mock_get_profile.return_value = mock_profile

        # Mock active strategy
        mock_strategy = MagicMock()
        mock_strategy.strategy_text = "Test strategy"
        mock_strategy.version = 1
        mock_get_strategy.return_value = mock_strategy

        # Mock conversation history
        mock_load_context.return_value = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "How are you?"}
        ]

        messages, snapshot = _build_reasoner_messages(self.chat_id, turns=5)

        # Verify messages structure
        assert len(messages) >= 3  # system messages + user message
        system_messages = [msg for msg in messages if isinstance(msg, dict) and msg.get("role") == "system"]
        assert len(system_messages) >= 1
        user_messages = [msg for msg in messages if isinstance(msg, dict) and msg.get("role") == "user"]
        assert len(user_messages) >= 1

        # Verify snapshot
        assert "user: Hello" in snapshot
        assert "assistant: Hi" in snapshot
        assert "user: How are you?" in snapshot

    @patch('reasoner._load_payload')
    @patch('reasoner._build_reasoner_messages')
    @patch('reasoner.activate_new_strategy')
    @patch('reasoner.client')
    def test_run_reasoner_for_chat_success(self, mock_client, mock_activate, mock_build_messages, mock_load_payload):
        """Test successful reasoner execution"""
        from reasoner import run_reasoner_for_chat

        # Mock payload
        mock_load_payload.return_value = {"model": "test", "messages": []}

        # Mock message building
        mock_build_messages.return_value = ([{"role": "user", "content": "test"}], "snapshot")

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "New strategy text"
        mock_client.chat.completions.create.return_value = mock_response

        # Mock strategy activation
        mock_activate.return_value = 2

        result = run_reasoner_for_chat(self.chat_id)

        # Verify calls
        mock_load_payload.assert_called_once()
        mock_build_messages.assert_called_once_with(self.chat_id)
        mock_client.chat.completions.create.assert_called_once()
        mock_activate.assert_called_once_with(self.chat_id, strategy_text="New strategy text", source_snapshot="snapshot")

        assert result == 2

    @patch('reasoner._load_payload')
    @patch('reasoner._build_reasoner_messages')
    @patch('reasoner.client')
    def test_run_reasoner_for_chat_api_error(self, mock_client, mock_build_messages, mock_load_payload):
        """Test reasoner execution with API error"""
        from reasoner import run_reasoner_for_chat

        mock_load_payload.return_value = {"model": "test", "messages": []}
        mock_build_messages.return_value = ([], "")

        mock_client.chat.completions.create.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            run_reasoner_for_chat(self.chat_id)

    @patch('reasoner.get_profile')
    @patch('reasoner.get_active_strategy')
    @patch('reasoner.load_last_context')
    @patch('reasoner._load_payload')
    @patch('reasoner.activate_new_strategy')
    @patch('reasoner.client')
    def test_update_chat_context_and_profile_success(self, mock_client, mock_activate, mock_load_payload,
                                                    mock_load_context, mock_get_strategy, mock_get_profile):
        """Test successful context and profile update"""
        from reasoner import update_chat_context_and_profile

        # Mock profile
        mock_profile = MagicMock()
        mock_profile.initial_context = "Initial context"
        mock_profile.objective = "Test objective"
        mock_profile.instructions = "Test instructions"
        mock_get_profile.return_value = mock_profile

        # Mock strategy
        mock_strategy = MagicMock()
        mock_strategy.strategy_text = "Previous strategy"
        mock_get_strategy.return_value = mock_strategy

        # Mock context
        mock_load_context.return_value = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"}
        ]

        # Mock payload
        mock_load_payload.return_value = {"model": "test", "messages": []}

        # Mock OpenAI response with JSON
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "perfil_update": "New profile info",
            "contexto_prioritario": "Important context",
            "estrategia": "New strategy"
        })
        mock_client.chat.completions.create.return_value = mock_response

        # Mock strategy activation
        mock_activate.return_value = 3

        # Change to temp directory so files are created there
        original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        try:
            # Patch HERE to use temp directory
            with patch('reasoner.HERE', self.temp_dir):
                result = update_chat_context_and_profile(self.chat_id)
        finally:
            os.chdir(original_cwd)

        # Verify result
        assert result["version"] == 3
        assert result["wrote_contexto"] is True
        assert result["wrote_perfil"] is True

        # Verify files were created
        contexto_path = os.path.join(self.temp_dir, "contextos", f"chat_{self.chat_id}", "contexto.txt")
        perfil_path = os.path.join(self.temp_dir, "contextos", f"chat_{self.chat_id}", "perfil.txt")

        assert os.path.exists(contexto_path)
        assert os.path.exists(perfil_path)

        # Verify file contents
        with open(contexto_path, 'r', encoding='utf-8') as f:
            contexto_content = f.read()
            assert "CONTEXTO PRIORITARIO:" in contexto_content
            assert "Important context" in contexto_content
            assert "ESTRATEGIA:" in contexto_content
            assert "New strategy" in contexto_content

        with open(perfil_path, 'r', encoding='utf-8') as f:
            perfil_content = f.read()
            assert "New profile info" in perfil_content

    @patch('reasoner.get_profile')
    @patch('reasoner.get_active_strategy')
    @patch('reasoner.load_last_context')
    @patch('reasoner._load_payload')
    @patch('reasoner.activate_new_strategy')
    @patch('admin_db.get_session')
    @patch('reasoner.client')
    def test_update_chat_context_and_profile_json_parse_error(self, mock_client, mock_get_session_db, mock_activate, mock_load_payload,
                                                             mock_load_context, mock_get_strategy, mock_get_profile):
        """Test context update with malformed JSON response"""
        from reasoner import update_chat_context_and_profile

        # Setup mocks
        mock_profile = MagicMock()
        mock_profile.initial_context = ""
        mock_profile.objective = "Test"
        mock_profile.instructions = ""
        mock_get_profile.return_value = mock_profile

        mock_strategy = MagicMock()
        mock_strategy.strategy_text = ""
        mock_get_strategy.return_value = mock_strategy

        mock_load_context.return_value = [{"role": "user", "content": "test"}]
        mock_load_payload.return_value = {"model": "test", "messages": []}

        # Mock response with malformed JSON
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "perfil_update: New info\ncontexto_prioritario: Context\nestrategia: Strategy"
        mock_client.chat.completions.create.return_value = mock_response

        # Mock database session for profile update
        mock_session = MagicMock()
        mock_get_session_db.return_value = mock_session
        mock_activate.return_value = 2

        # Change to temp directory so files are created there
        original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        try:
            # Patch HERE to use temp directory
            with patch('reasoner.HERE', self.temp_dir):
                result = update_chat_context_and_profile(self.chat_id)
        finally:
            os.chdir(original_cwd)

        # Should handle gracefully with fallback parsing
        assert result["version"] == 2
        assert isinstance(result["wrote_contexto"], bool)
        assert isinstance(result["wrote_perfil"], bool)

    @patch('reasoner.get_profile')
    @patch('reasoner.get_active_strategy')
    @patch('reasoner.load_last_context')
    @patch('reasoner._load_payload')
    @patch('reasoner.activate_new_strategy')
    @patch('admin_db.get_session')
    @patch('reasoner.client')
    def test_update_chat_context_and_profile_no_profile(self, mock_client, mock_get_session_db, mock_activate, mock_load_payload,
                                                       mock_load_context, mock_get_strategy, mock_get_profile):
        """Test context update when no profile exists"""
        from reasoner import update_chat_context_and_profile

        mock_get_profile.return_value = None
        mock_get_strategy.return_value = None
        mock_load_context.return_value = []
        mock_load_payload.return_value = {"model": "test", "messages": []}

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "perfil_update": "",
            "contexto_prioritario": "",
            "estrategia": "Strategy only"
        })
        mock_client.chat.completions.create.return_value = mock_response

        # Mock database session for profile update
        mock_session = MagicMock()
        mock_get_session_db.return_value = mock_session
        mock_activate.return_value = 1

        # Change to temp directory so files are created there
        original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        try:
            # Patch HERE to use temp directory
            with patch('reasoner.HERE', self.temp_dir):
                result = update_chat_context_and_profile(self.chat_id)
        finally:
            os.chdir(original_cwd)

        # Should handle gracefully
        assert result["version"] == 1
        assert isinstance(result["wrote_contexto"], bool)
        assert isinstance(result["wrote_perfil"], bool)

    def test_payload_file_not_found(self):
        """Test handling of missing payload file"""
        from reasoner import _load_payload

        # Patch the global variable to point to non-existent file
        with patch('reasoner.REASONER_PAYLOAD_PATH', "/non/existent/file.json"):
            with pytest.raises(FileNotFoundError):
                _load_payload()

    def test_payload_file_invalid_json(self):
        """Test handling of invalid JSON in payload file"""
        from reasoner import _load_payload

        # Create invalid JSON file
        invalid_path = os.path.join(self.temp_dir, "invalid.json")
        with open(invalid_path, 'w', encoding='utf-8') as f:
            f.write("invalid json content {")

        # Patch the global variable directly
        with patch('reasoner.REASONER_PAYLOAD_PATH', invalid_path):
            with pytest.raises(json.JSONDecodeError):
                _load_payload()
