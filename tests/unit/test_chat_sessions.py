import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from chat_sessions import (
    initialize_db,
    save_context,
    load_last_context,
    clear_conversation_history,
    clear_all_conversation_histories,
    add_or_update_contact,
    upsert_profile,
    get_profile,
    is_ready_to_reply,
    increment_reply_counter,
    reset_reply_counter,
    get_reply_counter,
    get_active_strategy,
    activate_new_strategy,
)


class TestChatSessions:
    """Comprehensive tests for chat_sessions.py module"""

    def test_initialize_db(self):
        """Test database initialization"""
        with patch('chat_sessions.initialize_schema') as mock_init:
            initialize_db()
            mock_init.assert_called_once()

    @patch('chat_sessions.get_session')
    @patch('chat_sessions.encrypt_text')
    def test_save_context(self, mock_encrypt, mock_session):
        """Test saving conversation context"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        test_context = [{"role": "user", "content": "Hello"}]
        save_context("test_chat_123", test_context)

        mock_encrypt.assert_called_once()
        mock_session_instance.add.assert_called_once()
        mock_session_instance.commit.assert_called_once()
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    @patch('chat_sessions.decrypt_text')
    def test_load_last_context_success(self, mock_decrypt, mock_session):
        """Test loading last conversation context successfully"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        # Mock the query result
        mock_row = MagicMock()
        mock_row.context = "encrypted_data"
        mock_session_instance.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_row

        mock_decrypt.return_value = '[{"role": "user", "content": "Hello"}]'

        result = load_last_context("test_chat_123")

        assert result == [{"role": "user", "content": "Hello"}]
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_load_last_context_no_data(self, mock_session):
        """Test loading context when no data exists"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = load_last_context("test_chat_123")

        assert result == []
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    @patch('chat_sessions.decrypt_text')
    def test_load_last_context_decrypt_error(self, mock_decrypt, mock_session):
        """Test loading context with decryption error"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        mock_row = MagicMock()
        mock_row.context = "encrypted_data"
        mock_session_instance.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_row

        mock_decrypt.side_effect = Exception("Decrypt failed")

        result = load_last_context("test_chat_123")

        assert result == []
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_clear_conversation_history(self, mock_session):
        """Test clearing conversation history for a specific chat"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        # Mock query with count and delete
        mock_query = MagicMock()
        mock_query.count.return_value = 5
        mock_session_instance.query.return_value.filter.return_value = mock_query

        result = clear_conversation_history("test_chat_123")

        assert result == 5
        mock_query.delete.assert_called_once_with(synchronize_session=False)
        mock_session_instance.commit.assert_called_once()
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_clear_all_conversation_histories(self, mock_session):
        """Test clearing all conversation histories"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        mock_query = MagicMock()
        mock_query.count.return_value = 15
        mock_session_instance.query.return_value = mock_query

        result = clear_all_conversation_histories()

        assert result == 15
        mock_query.delete.assert_called_once_with(synchronize_session=False)
        mock_session_instance.commit.assert_called_once()
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_add_or_update_contact_new(self, mock_session):
        """Test adding a new contact"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        mock_session_instance.get.return_value = None  # Contact doesn't exist

        add_or_update_contact("test_chat_123", "John Doe", True)

        # Should add new contact
        assert mock_session_instance.add.called
        mock_session_instance.commit.assert_called_once()
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_add_or_update_contact_existing(self, mock_session):
        """Test updating an existing contact"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        mock_contact = MagicMock()
        mock_session_instance.get.return_value = mock_contact

        add_or_update_contact("test_chat_123", "Jane Doe", False)

        # Should update existing contact
        assert mock_contact.name == "Jane Doe"
        assert not mock_contact.auto_enabled
        assert mock_contact.updated_at is not None
        mock_session_instance.commit.assert_called_once()
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_upsert_profile_new(self, mock_session):
        """Test creating a new chat profile"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        mock_session_instance.get.return_value = None  # Profile doesn't exist

        upsert_profile("test_chat_123", "Initial context", "Test objective", "Instructions", True)

        # Should add new profile and counter
        assert mock_session_instance.add.call_count == 2  # Profile and counter
        mock_session_instance.commit.assert_called_once()
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_upsert_profile_existing(self, mock_session):
        """Test updating an existing chat profile"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        mock_profile = MagicMock()
        mock_counter = MagicMock()
        mock_session_instance.get.side_effect = [mock_profile, mock_counter]

        upsert_profile("test_chat_123", "Updated context", "Updated objective")

        # Should update existing profile
        assert mock_profile.initial_context == "Updated context"
        assert mock_profile.objective == "Updated objective"
        assert mock_profile.is_ready
        mock_session_instance.commit.assert_called_once()
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_get_profile(self, mock_session):
        """Test getting a chat profile"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        mock_profile = MagicMock()
        mock_session_instance.get.return_value = mock_profile

        result = get_profile("test_chat_123")

        assert result == mock_profile
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_is_ready_to_reply_true(self, mock_session):
        """Test checking if chat is ready to reply - positive case"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        mock_contact = MagicMock()
        mock_contact.auto_enabled = True
        mock_profile = MagicMock()
        mock_profile.is_ready = True

        mock_session_instance.get.side_effect = [mock_contact, mock_profile]

        result = is_ready_to_reply("test_chat_123")

        assert result
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_is_ready_to_reply_false_no_contact(self, mock_session):
        """Test checking if chat is ready to reply - no contact"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        mock_session_instance.get.side_effect = [None, None]  # No contact, no profile

        result = is_ready_to_reply("test_chat_123")

        assert not result
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_increment_reply_counter_new(self, mock_session):
        """Test incrementing reply counter for new chat"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        mock_session_instance.get.return_value = None  # No counter exists

        result = increment_reply_counter("test_chat_123")

        assert result == 1
        mock_session_instance.add.assert_called_once()
        mock_session_instance.commit.assert_called_once()
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_increment_reply_counter_existing(self, mock_session):
        """Test incrementing reply counter for existing chat"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        mock_counter = MagicMock()
        mock_counter.assistant_replies_count = 5
        mock_session_instance.get.return_value = mock_counter

        result = increment_reply_counter("test_chat_123")

        assert result == 6
        assert mock_counter.assistant_replies_count == 6
        mock_session_instance.commit.assert_called_once()
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_reset_reply_counter(self, mock_session):
        """Test resetting reply counter"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        mock_counter = MagicMock()
        mock_counter.assistant_replies_count = 10
        mock_session_instance.get.return_value = mock_counter

        reset_reply_counter("test_chat_123")

        assert mock_counter.assistant_replies_count == 0
        mock_session_instance.commit.assert_called_once()
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_get_reply_counter_existing(self, mock_session):
        """Test getting reply counter for existing chat"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        mock_counter = MagicMock()
        mock_counter.assistant_replies_count = 7
        mock_session_instance.get.return_value = mock_counter

        result = get_reply_counter("test_chat_123")

        assert result == 7
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_get_reply_counter_none(self, mock_session):
        """Test getting reply counter when none exists"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        mock_session_instance.get.return_value = None

        result = get_reply_counter("test_chat_123")

        assert result == 0
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_get_active_strategy(self, mock_session):
        """Test getting active strategy"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        mock_strategy = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_strategy
        mock_session_instance.query.return_value = mock_query

        result = get_active_strategy("test_chat_123")

        assert result == mock_strategy
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_activate_new_strategy_first(self, mock_session):
        """Test activating first strategy for a chat"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        # Mock no previous strategies
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = None
        mock_session_instance.query.return_value = mock_query

        # Mock no counter exists
        mock_session_instance.get.return_value = None

        result = activate_new_strategy("test_chat_123", "Test strategy", "snapshot")

        assert result == 1
        # Should deactivate previous (but none exist), add new strategy, create counter
        assert mock_session_instance.add.call_count == 2  # Strategy and counter
        mock_session_instance.commit.assert_called_once()
        mock_session_instance.close.assert_called_once()

    @patch('chat_sessions.get_session')
    def test_activate_new_strategy_subsequent(self, mock_session):
        """Test activating subsequent strategy"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        # Mock previous strategy exists
        mock_last_strategy = MagicMock()
        mock_last_strategy.version = 2
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_last_strategy
        mock_session_instance.query.return_value = mock_query

        # Mock counter exists
        mock_counter = MagicMock()
        mock_session_instance.get.return_value = mock_counter

        result = activate_new_strategy("test_chat_123", "New strategy")

        assert result == 3  # Next version after 2
        # Should update counter strategy_version and last_reasoned_at
        assert mock_counter.strategy_version == 3
        assert mock_counter.last_reasoned_at is not None
        mock_session_instance.commit.assert_called_once()
        mock_session_instance.close.assert_called_once()