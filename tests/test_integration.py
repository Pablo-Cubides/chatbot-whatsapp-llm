"""
Integration tests for WhatsApp automation and manual messaging system.
These tests cover the complete end-to-end flows that are critical for production.
"""
import pytest
import json
from unittest.mock import Mock, patch
from pathlib import Path

# Import modules to test
import sys
sys.path.append(str(Path(__file__).parent.parent))

from admin_panel import app
from fastapi.testclient import TestClient


class TestManualMessagingFlow:
    """Test the complete manual messaging workflow"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.client = TestClient(app)
        self.test_data_dir = Path(__file__).parent / "test_data"
        self.test_data_dir.mkdir(exist_ok=True)
        
        # Create test queue file
        self.queue_file = self.test_data_dir / "manual_queue.json"
        
    def teardown_method(self):
        """Cleanup after each test"""
        if self.queue_file.exists():
            self.queue_file.unlink()
    
    def test_complete_manual_message_flow(self, sample_manual_queue):
        """
        Test complete flow: API request -> Queue -> Processing -> Sending
        This is the most critical flow for business value.
        """
        # Step 1: Send message via API
        message_data = {
            "chat_id": "+573107601252",
            "message": "Test message from automated test",
            "media": None
        }
        
        # Create the queue file beforehand so the API can write to it
        self.queue_file.write_text('[]', encoding='utf-8')
        
        # Mock only the path resolution in admin_panel
        with patch('admin_panel.os.path.dirname', return_value=str(self.test_data_dir.parent)):
            with patch('admin_panel.os.path.join', return_value=str(self.queue_file)):
                response = self.client.post("/api/whatsapp/send", json=message_data)
            assert response.status_code == 200
            
            response_data = response.json()
            assert response_data["success"] is True
            assert "enviado a cola" in response_data["message"]
        
        # Step 2: Verify message was queued
        assert self.queue_file.exists()
        with open(self.queue_file, 'r', encoding='utf-8') as f:
            queue = json.load(f)
        
        assert len(queue) == 1
        queued_message = queue[0]
        assert queued_message["chat_id"] == message_data["chat_id"]
        assert queued_message["message"] == message_data["message"]
        assert queued_message["status"] == "pending"
        assert "timestamp" in queued_message
        assert "id" in queued_message
    
    @patch('whatsapp_automator.send_manual_message')
    def test_queue_processing_success(self, mock_send_manual):
        """Test successful processing of queued messages"""
        # Setup mock page and successful sending
        mock_page = Mock()
        mock_send_manual.return_value = True
        
        # Create test queue
        test_queue = [{
            "id": "test_123",
            "chat_id": "+573107601252",
            "message": "Test queue processing",
            "timestamp": "2025-09-16T10:30:00",
            "status": "pending"
        }]
        
        with open(self.queue_file, 'w', encoding='utf-8') as f:
            json.dump(test_queue, f)
        
        # Import and test queue processing
        import whatsapp_automator
        
        # Better approach: create the queue file directly
        with open(self.queue_file, 'w', encoding='utf-8') as f:
            json.dump(test_queue, f)
        
        with patch.object(whatsapp_automator, 'os') as mock_os:
            mock_os.path.dirname.return_value = str(self.test_data_dir.parent)
            mock_os.path.join.return_value = str(self.queue_file)
            mock_os.path.exists.return_value = True
            
            result = whatsapp_automator.process_manual_queue(mock_page)
            
            assert result is True
            mock_send_manual.assert_called_once()
        
        # Verify message was marked as sent
        with open(self.queue_file, 'r', encoding='utf-8') as f:
            updated_queue = json.load(f)
        
        assert updated_queue[0]["status"] == "sent"
        assert "sent_timestamp" in updated_queue[0]
    
    @patch('whatsapp_automator.send_manual_message')
    def test_queue_processing_failure_handling(self, mock_send_manual):
        """Test proper handling of message sending failures"""
        # Setup mock to simulate sending failure
        mock_page = Mock()
        mock_send_manual.return_value = False
        
        test_queue = [{
            "id": "test_fail_123",
            "chat_id": "+573107601252",
            "message": "Test failure handling",
            "timestamp": "2025-09-16T10:30:00",
            "status": "pending"
        }]
        
        with open(self.queue_file, 'w', encoding='utf-8') as f:
            json.dump(test_queue, f)
        
        import whatsapp_automator
        
        with patch.object(whatsapp_automator, 'os') as mock_os:
            mock_os.path.dirname.return_value = str(self.test_data_dir.parent)
            mock_os.path.join.return_value = str(self.queue_file)
            mock_os.path.exists.return_value = True
            
            result = whatsapp_automator.process_manual_queue(mock_page)
            
            assert result is False  # Should return False when sending fails
        
        # Verify message was marked as failed (prevents infinite loops)
        with open(self.queue_file, 'r', encoding='utf-8') as f:
            updated_queue = json.load(f)
        
        assert updated_queue[0]["status"] == "failed"
        assert "failed_timestamp" in updated_queue[0]


class TestWhatsAppAutomationFlow:
    """Test WhatsApp automation core functionality"""
    
    def test_message_detection_logic(self, mock_page, sample_whatsapp_elements):
        """Test the core message detection algorithm"""
        import whatsapp_automator

        # Mock page elements for unread messages
        mock_rows = Mock()
        mock_rows.count.return_value = 1

        # Mock individual row with unread badge
        mock_row = Mock()
        mock_spans = [Mock(), Mock(), Mock()]
        mock_spans[1].inner_text.return_value = "2"  # Unread count
        mock_spans[1].inner_text.side_effect = None  # Reset side_effect
        mock_row.locator.return_value.all.return_value = mock_spans
        mock_rows.nth.return_value = mock_row

        # Mock the chat_id extraction
        mock_chat_element = Mock()
        mock_chat_element.get_attribute.return_value = "+573107601252"
        mock_chat_element.inner_text.return_value = "+573107601252"
        mock_chat_elements = Mock()
        mock_chat_elements.count.return_value = 1
        mock_chat_elements.first = mock_chat_element
        mock_row.locator.side_effect = lambda sel: mock_chat_elements if 'span[title]' in sel else mock_row.locator.return_value

        mock_page.locator.return_value = mock_rows
        mock_page.wait_for_selector.return_value = True

        # Mock clicking on row and extracting message
        mock_last_msg = Mock()
        mock_last_msg.locator.return_value.count.return_value = 0  # Not from bot
        mock_last_msg.get_attribute.return_value = ""  # Not message-out class
        
        # Mock the text extraction with span.selectable-text
        mock_text_elem = Mock()
        mock_text_elem.inner_text.return_value = "Test incoming message"
        mock_text_elem.count.return_value = 1
        
        mock_text_locator = Mock()
        mock_text_locator.first = mock_text_elem
        mock_text_locator.count.return_value = 1
        
        def mock_last_msg_locator(selector):
            if "message-out" in selector or "outgoing" in selector:
                return Mock(count=lambda: 0)  # Not from bot
            elif "span.selectable-text" in selector:
                return mock_text_locator
            return Mock(count=lambda: 0)
        
        mock_last_msg.locator.side_effect = mock_last_msg_locator

        mock_msgs = Mock()
        mock_msgs.count.return_value = 1
        mock_msgs.last = mock_last_msg

        # Setup page.locator to return different mocks based on selector
        def mock_locator(selector):
            if "#pane-side" in selector:
                return Mock(locator=lambda s: mock_rows)
            elif "div[data-testid='msg-container']" in selector:
                return mock_msgs
            return Mock()

        mock_page.locator.side_effect = mock_locator        # Mock permissions check
        with patch('whatsapp_automator.chat_sessions.is_ready_to_reply', return_value=True):
            with patch.object(whatsapp_automator, 'log'):
                # The codebase now uses DB-backed ChatCounter for cooldowns. Mock the
                # get_session() function to return a fake session whose query(...).filter(...).first()
                # returns None (meaning no recent reply recorded), so fetch_new_message will proceed.
                mock_session = Mock()
                # Chain the call: session.query(...).filter(...).first() -> None
                mock_session.query.return_value.filter.return_value.first.return_value = None
                with patch('whatsapp_automator.get_session', return_value=mock_session):
                    chat_id, message = whatsapp_automator.fetch_new_message(mock_page, respond_to_all=True)

        # Should detect and return the message
        assert chat_id is not None
        assert message is not None
        assert message == "Test incoming message"
    
    def test_multiple_chat_navigation_strategies(self, mock_page):
        """Test the multi-strategy chat navigation system"""
        import whatsapp_automator
        
        # Mock search activation - first selector succeeds
        mock_page.click.return_value = None
        mock_page.wait_for_timeout.return_value = None
        
        # Mock search input - properly set up for the selector logic
        mock_search_input = Mock()
        mock_search_input.count.return_value = 1
        mock_search_input.fill = Mock()
        mock_search_input.type = Mock()
        mock_search_input.press = Mock()
        
        # Mock the search input locator chain
        mock_search_locator = Mock()
        mock_search_locator.first = mock_search_input
        mock_search_locator.count.return_value = 1
        
        # Mock conversation compose box (for chat verification)
        mock_compose_box = Mock()
        mock_compose_box.count.return_value = 1  # Chat is open
        
        # Setup page.locator to return appropriate mocks based on selector
        def mock_locator(selector):
            if "chat-list-search" in selector and "contenteditable" in selector:
                return mock_search_locator
            elif "conversation-compose-box-input" in selector:
                return mock_compose_box
            else:
                # Default mock for other selectors
                return Mock(count=lambda: 0, first=Mock())
        
        mock_page.locator.side_effect = mock_locator
        
        # Mock send_reply_with_typing success
        with patch.object(whatsapp_automator, 'send_reply_with_typing', return_value=True):
            with patch.object(whatsapp_automator, 'cleanup_search_and_return_to_normal'):
                with patch.object(whatsapp_automator, 'exit_chat_safely'):
                    with patch.object(whatsapp_automator, 'log'):
                        result = whatsapp_automator.send_manual_message(
                            mock_page, 
                            "+573107601252", 
                            "Test message", 
                            per_char_delay=0.01
                        )
        
        assert result is True
        mock_search_input.fill.assert_called_with("")  # Clear search
        mock_search_input.type.assert_called_with("+573107601252")


class TestLLMIntegrationFlow:
    """Test LLM integration and conversation management"""
    
    @patch('stub_chat.chat')
    def test_conversation_context_management(self, mock_chat, sample_chat_history):
        """Test conversation context loading and saving"""
        import chat_sessions
        
        # Mock the LLM response
        mock_chat.return_value = "Esta es una respuesta de prueba del LLM"
        
        # Test context initialization
        chat_sessions.initialize_db()
        
        test_chat_id = "test_chat_12345"
        
        # Save initial context
        chat_sessions.save_context(test_chat_id, sample_chat_history)
        
        # Load and verify context
        loaded_history = chat_sessions.load_last_context(test_chat_id)
        assert loaded_history == sample_chat_history
        
        # Test adding new message to context
        new_message = {"role": "user", "content": "Nueva pregunta de test"}
        updated_history = loaded_history + [new_message]
        
        # Test LLM call with context
        response = mock_chat(new_message["content"], test_chat_id, updated_history)
        
        assert response == "Esta es una respuesta de prueba del LLM"
        mock_chat.assert_called_once_with(
            new_message["content"], 
            test_chat_id, 
            updated_history
        )
    
    def test_model_management_system(self):
        """Test model switching and management"""
        import model_manager
        
        mm = model_manager.ModelManager()
        
        # Test model selection logic
        test_chat_id = "test_model_chat"
        message_count = 5
        
        chosen_model = mm.choose_model_for_conversation(test_chat_id, message_count)
        
        # Should return a valid model name
        assert chosen_model is not None
        assert isinstance(chosen_model, str)
        assert len(chosen_model) > 0


class TestAdminPanelAPI:
    """Test Admin Panel API endpoints"""
    
    def setup_method(self):
        """Setup test client"""
        from admin_panel import verify_token
        from admin_db import initialize_schema
        
        # Initialize database schema for tests
        try:
            initialize_schema()
        except Exception:
            # If schema already exists, continue
            pass
        
        # Mock authentication for tests
        def mock_verify_token():
            return {"user": "test_user"}
        
        app.dependency_overrides[verify_token] = mock_verify_token
        self.client = TestClient(app)
        
    def teardown_method(self):
        """Cleanup after each test"""
        app.dependency_overrides.clear()
    
    def test_lm_studio_status_endpoint(self):
        """Test LM Studio status checking"""
        response = self.client.get("/api/lmstudio/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] in ["connected", "disconnected", "error"]
    
    def test_whatsapp_status_endpoint(self):
        """Test WhatsApp automator status"""
        response = self.client.get("/api/whatsapp/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] in ["running", "stopped", "error"]
    
    def test_models_list_endpoint(self):
        """Test models listing"""
        response = self.client.get("/api/models")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_send_message_validation(self):
        """Test message sending input validation"""
        # Test missing required fields
        response = self.client.post("/api/whatsapp/send", json={})
        assert response.status_code == 422  # Validation error
        
        # Test valid request structure
        valid_data = {
            "chat_id": "+573107601252",
            "message": "Test validation message"
        }
        response = self.client.post("/api/whatsapp/send", json=valid_data)
        # For a valid payload we expect a successful validation and enqueue (200)
        assert response.status_code == 200
        resp_json = response.json()
        assert isinstance(resp_json, dict)
        # Require either explicit success True or a human-readable message
        msg = resp_json.get("message")
        assert resp_json.get("success") is True or (isinstance(msg, str) and msg.strip())


class TestSystemIntegration:
    """Test complete system integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_complete_conversation_flow(self, mock_env_vars):
        """
        Test complete conversation flow from message detection to response
        This simulates a real user conversation scenario
        """
        import whatsapp_automator
        import chat_sessions
        
        # Initialize system
        chat_sessions.initialize_db()
        
        test_chat_id = "integration_test_chat"
        incoming_message = "Hola, necesito ayuda con un producto"
        
        # Mock the complete flow
        with patch.object(whatsapp_automator, 'fetch_new_message') as mock_fetch:
            mock_fetch.return_value = (test_chat_id, incoming_message)
            
            with patch('stub_chat.chat') as mock_chat:
                mock_chat.return_value = "¡Hola! Claro que puedo ayudarte con información sobre productos. ¿Qué necesitas saber específicamente?"
                
                with patch.object(whatsapp_automator, 'send_reply_with_typing') as mock_send:
                    mock_send.return_value = True
                    
                    # This simulates one iteration of the main loop
                    chat_id, message = whatsapp_automator.fetch_new_message(Mock(), False)
                    
                    if chat_id and message:
                        # Clear any existing context first
                        chat_sessions.save_context(chat_id, [])
                        
                        # Load context and add new message
                        history = chat_sessions.load_last_context(chat_id) or []
                        history.append({"role": "user", "content": message})
                        
                        # Generate response
                        from stub_chat import chat as stub_chat
                        reply = stub_chat(message, chat_id, history)
                        
                        # Save updated context
                        history.append({"role": "assistant", "content": reply})
                        chat_sessions.save_context(chat_id, history)
                        
                        # Send response
                        sent = whatsapp_automator.send_reply_with_typing(Mock(), chat_id, reply, 0.01)
                        
                        assert sent is True
                        assert len(history) == 2  # User message + bot response
                        assert history[0]["role"] == "user"
                        assert history[1]["role"] == "assistant"
    
    def test_error_recovery_mechanisms(self):
        """Test system behavior under error conditions"""
        import whatsapp_automator
        
        # Test handling of page errors
        mock_page = Mock()
        mock_page.wait_for_selector.side_effect = Exception("Timeout error")
        
        # Should handle errors gracefully without crashing
        try:
            result = whatsapp_automator.fetch_new_message(mock_page, False)
            # Should return None, None for errors
            assert result == (None, None)
        except Exception:
            pytest.fail("System should handle errors gracefully")
    
    def test_performance_benchmarks(self):
        """Basic performance tests for critical functions"""
        import time
        import whatsapp_automator
        
        # Test message processing speed
        start_time = time.time()
        
        # Simulate processing 10 messages
        for i in range(10):
            mock_page = Mock()
            mock_page.locator.return_value.count.return_value = 0
            whatsapp_automator.fetch_new_message(mock_page, False)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should process messages efficiently (< 1 second for 10 messages)
        assert processing_time < 1.0, f"Message processing too slow: {processing_time}s"


if __name__ == "__main__":
    # Run tests with coverage
    pytest.main([
        __file__,
        "-v",
        "--cov=../",
        "--cov-report=html",
        "--cov-report=term-missing"
    ])