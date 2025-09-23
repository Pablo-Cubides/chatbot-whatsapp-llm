"""
Unit tests for WhatsApp automation core functionality.
Tests the critical chat detection and message processing logic.
"""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))


class TestWhatsAppMessageDetection:
    """Test message detection and chat verification logic"""
    
    def test_fetch_new_message_error_handling(self):
        """Test that fetch_new_message handles errors gracefully"""
        import whatsapp_automator
        
        mock_page = Mock()
        # Simulate timeout/error condition
        mock_page.wait_for_selector.side_effect = Exception("Timeout")
        
        # Test error handling
        with patch.object(whatsapp_automator, 'log'):
            chat_id, message = whatsapp_automator.fetch_new_message(mock_page, respond_to_all=False)
        
        # Should return None values on error
        assert chat_id is None
        assert message is None
    
    def test_message_extraction_logic(self):
        """Test basic function call structure without complex mocking"""
        import whatsapp_automator
        
        mock_page = Mock()
        
        # Mock the function to return None (simulating no new messages)
        # This tests that the function can be called without crashing
        mock_page.wait_for_selector.side_effect = Exception("Timeout")
        
        # Test that function handles exceptions gracefully
        with patch.object(whatsapp_automator, 'log'):
            chat_id, message = whatsapp_automator.fetch_new_message(mock_page, respond_to_all=False)
        
        # Should return None values when no messages or errors occur
        assert chat_id is None
        assert message is None
    
    def test_send_reply_function_basic(self):
        """Test that send_reply_with_typing can be called without crashing"""
        import whatsapp_automator
        
        mock_page = Mock()
        
        # Mock all the page interactions to return safely
        mock_page.locator.return_value.count.return_value = 0  # No elements found
        mock_page.wait_for_timeout.return_value = None
        
        # Test the function with basic parameters
        with patch.object(whatsapp_automator, 'log'):
            result = whatsapp_automator.send_reply_with_typing(
                mock_page, 
                "+573107601252",
                "Test message", 
                per_char_delay=0.01
            )
        
        # Should return False when no input elements are found
        assert result is False


class TestChatNavigation:
    """Test chat search and navigation functionality"""
    
    def test_send_manual_message_error_handling(self):
        """Test manual message function error handling"""
        import whatsapp_automator
        
        mock_page = Mock()
        mock_page.wait_for_timeout.return_value = None
        mock_page.click.return_value = None
        
        # Mock send_reply_with_typing to return False (failure)
        with patch.object(whatsapp_automator, 'send_reply_with_typing', return_value=False):
            with patch.object(whatsapp_automator, 'log'):
                result = whatsapp_automator.send_manual_message(
                    mock_page,
                    "+573107601252",
                    "Test manual message"
                )
        
        # Should return False when sending fails
        assert result is False


class TestMessageSending:
    """Test message composition and sending functionality"""
    
    def test_send_reply_with_typing_no_input(self):
        """Test send_reply_with_typing when no input field is found"""
        import whatsapp_automator
        
        mock_page = Mock()
        
        # Mock _get_message_input to return None (no input found)
        with patch.object(whatsapp_automator, '_get_message_input', return_value=None):
            with patch.object(whatsapp_automator, 'log'):
                result = whatsapp_automator.send_reply_with_typing(
                    mock_page, 
                    "+573107601252",
                    "Test message", 
                    per_char_delay=0.01
                )
        
        # Should return False when no input is found
        assert result is False
    
    def test_send_reply_with_typing_success_mock(self):
        """Test send_reply_with_typing with successful mock"""
        import whatsapp_automator
        
        mock_page = Mock()
        mock_input = Mock()
        
        # Mock successful input finding and typing
        with patch.object(whatsapp_automator, '_get_message_input', return_value=mock_input):
            with patch.object(whatsapp_automator, 'log'):
                result = whatsapp_automator.send_reply_with_typing(
                    mock_page, 
                    "+573107601252",
                    "Test message", 
                    per_char_delay=0.01
                )
        
        # Should return True when mocked successfully
        assert result is True


class TestErrorHandling:
    """Test error handling and recovery mechanisms"""
    
    def test_element_timeout_handling(self):
        """Test handling of element timeout errors"""
        import whatsapp_automator
        
        mock_page = Mock()
        
        # Mock timeout exception
        mock_page.wait_for_selector.side_effect = Exception("Timeout waiting for selector")
        mock_page.locator.return_value.count.side_effect = Exception("Element not found")
        
        # Should handle errors gracefully
        with patch.object(whatsapp_automator, 'log'):
            try:
                chat_id, message = whatsapp_automator.fetch_new_message(mock_page, False)
                # Should return None values on error
                assert chat_id is None
                assert message is None
            except Exception:
                pytest.fail("Should handle timeouts gracefully")
    
    def test_navigation_failure_recovery(self):
        """Test recovery from navigation failures"""
        import whatsapp_automator
        
        mock_page = Mock()
        
        # Mock navigation failure
        mock_page.click.side_effect = Exception("Click failed")
        mock_page.locator.return_value.click.side_effect = Exception("Element click failed")
        
        # Should attempt recovery or fail gracefully
        with patch.object(whatsapp_automator, 'log'):
            try:
                result = whatsapp_automator.send_manual_message(
                    mock_page,
                    "+573107601252",
                    "Test recovery message"
                )
                # Should return False on failure, not crash
                assert result is False
            except Exception:
                pytest.fail("Should handle navigation failures gracefully")
    
    def test_queue_corruption_handling(self):
        """Test handling of corrupted queue files"""
        import whatsapp_automator
        from pathlib import Path
        
        # Create test directory
        test_dir = Path(__file__).parent / "test_data"
        test_dir.mkdir(exist_ok=True)
        
        # Create corrupted queue file
        corrupt_queue_file = test_dir / "corrupt_queue.json"
        with open(corrupt_queue_file, 'w') as f:
            f.write('{"invalid": json content}')  # Invalid JSON
        
        mock_page = Mock()
        
        # Mock the file path
        with patch('os.path.join', return_value=str(corrupt_queue_file)):
            with patch('os.path.exists', return_value=True):
                with patch.object(whatsapp_automator, 'log'):
                    try:
                        result = whatsapp_automator.process_manual_queue(mock_page)
                        # Deterministic expectation: corrupted queue should not be processed successfully
                        assert result is False
                    except Exception as ex:
                        pytest.fail(f"Should handle corrupted JSON gracefully, but raised: {ex}")
        
        # Cleanup
        if corrupt_queue_file.exists():
            corrupt_queue_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])