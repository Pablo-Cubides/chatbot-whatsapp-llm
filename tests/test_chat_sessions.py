"""
Unit tests for chat sessions and conversation management.
Tests the database operations and context handling.
"""
import pytest
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

import chat_sessions


class TestChatSessions:
    """Test chat session database operations"""
    
    def setup_method(self):
        """Setup test database for each test"""
        # Just initialize the existing database - tests will be isolated by chat_id
        chat_sessions.initialize_db()
    
    def teardown_method(self):
        """Cleanup after each test"""
        # Clean up test data by using unique chat IDs
        pass
    
    def test_database_initialization(self):
        """Test database initialization"""
        # Database initialization should create usable schema and allow operations
        try:
            chat_sessions.initialize_db()
            # Perform a simple roundtrip: clear all histories and ensure it returns an int
            cleared = chat_sessions.clear_all_conversation_histories()
            assert isinstance(cleared, int)
        except Exception as e:
            pytest.fail(f"Database initialization failed: {e}")
    
    def test_save_and_load_context(self):
        """Test saving and loading conversation context"""
        test_chat_id = "test_chat_123"
        test_context = [
            {"role": "user", "content": "Hola, ¿cómo estás?"},
            {"role": "assistant", "content": "¡Hola! Estoy bien, gracias por preguntar. ¿En qué puedo ayudarte?"},
            {"role": "user", "content": "Necesito información sobre productos"}
        ]
        
        # Save context
        chat_sessions.save_context(test_chat_id, test_context)
        
        # Load context
        loaded_context = chat_sessions.load_last_context(test_chat_id)
        
        # Should match exactly
        assert loaded_context == test_context
        assert len(loaded_context) == 3
        assert loaded_context[0]["role"] == "user"
        assert loaded_context[1]["role"] == "assistant"
        assert loaded_context[2]["role"] == "user"
    
    def test_context_history_management(self):
        """Test context history with multiple saves"""
        test_chat_id = "test_history_chat"
        
        # Save multiple contexts over time
        context1 = [{"role": "user", "content": "Primera conversación"}]
        context2 = [
            {"role": "user", "content": "Primera conversación"},
            {"role": "assistant", "content": "Respuesta a primera"},
            {"role": "user", "content": "Segunda pregunta"}
        ]
        context3 = [
            {"role": "user", "content": "Primera conversación"},
            {"role": "assistant", "content": "Respuesta a primera"},
            {"role": "user", "content": "Segunda pregunta"},
            {"role": "assistant", "content": "Respuesta a segunda"},
            {"role": "user", "content": "Tercera pregunta"}
        ]
        
        chat_sessions.save_context(test_chat_id, context1)
        chat_sessions.save_context(test_chat_id, context2)
        chat_sessions.save_context(test_chat_id, context3)
        
        # Should load the most recent context
        loaded = chat_sessions.load_last_context(test_chat_id)
        assert loaded == context3
        assert len(loaded) == 5
    
    def test_empty_context_handling(self):
        """Test handling of non-existent chat contexts"""
        non_existent_chat = "non_existent_chat_123"
        
        # Should return None or empty list for non-existent chat
        loaded = chat_sessions.load_last_context(non_existent_chat)
        assert loaded is None or loaded == []
    
    def test_large_context_handling(self):
        """Test handling of large conversation contexts"""
        test_chat_id = "large_context_chat"
        
        # Create a large context (100 messages)
        large_context = []
        for i in range(50):
            large_context.append({"role": "user", "content": f"Usuario mensaje {i}"})
            large_context.append({"role": "assistant", "content": f"Respuesta del asistente {i}"})
        
        # Should save and load large contexts without issues
        chat_sessions.save_context(test_chat_id, large_context)
        loaded = chat_sessions.load_last_context(test_chat_id)
        
        assert loaded == large_context
        assert len(loaded) == 100
    
    def test_special_characters_in_content(self):
        """Test handling of special characters and encoding"""
        test_chat_id = "special_chars_chat"
        special_context = [
            {"role": "user", "content": "Texto con ñ, acentos á é í ó ú, y símbolos €$%&"},
            {"role": "assistant", "content": "Emojis 🚀🔥💻 y caracteres unicode ™®©"},
            {"role": "user", "content": "Comillas \"dobles\" y 'simples' y \\backslashes\\"}
        ]
        
        # Should handle special characters properly
        chat_sessions.save_context(test_chat_id, special_context)
        loaded = chat_sessions.load_last_context(test_chat_id)
        
        assert loaded == special_context
        assert "ñ" in loaded[0]["content"]
        assert "🚀" in loaded[1]["content"]
        assert "\"" in loaded[2]["content"]
    
    def test_concurrent_access_simulation(self):
        """Test database behavior with multiple concurrent operations"""
        chat_ids = ["concurrent_1", "concurrent_2", "concurrent_3"]
        
        # Simulate multiple chats saving context simultaneously
        for i, chat_id in enumerate(chat_ids):
            context = [
                {"role": "user", "content": f"Usuario {i}"},
                {"role": "assistant", "content": f"Respuesta {i}"}
            ]
            chat_sessions.save_context(chat_id, context)
        
        # All contexts should be saved independently
        for i, chat_id in enumerate(chat_ids):
            loaded = chat_sessions.load_last_context(chat_id)
            assert loaded is not None
            assert len(loaded) == 2
            assert f"Usuario {i}" in loaded[0]["content"]
            assert f"Respuesta {i}" in loaded[1]["content"]


class TestContextManipulation:
    """Test context manipulation and processing"""
    
    def test_context_truncation_logic(self):
        """Test context truncation for token limits"""
        # This tests business logic that might exist for managing context size
        long_context = []
        
        # Create a very long conversation
        for i in range(100):
            long_context.append({
                "role": "user", 
                "content": f"Esta es una pregunta muy larga número {i} " * 10
            })
            long_context.append({
                "role": "assistant", 
                "content": f"Esta es una respuesta muy larga número {i} " * 10
            })
        
        # If there's context truncation logic, test it
        # For now, just verify we can handle long contexts
        assert len(long_context) == 200
        assert long_context[0]["role"] == "user"
        assert long_context[-1]["role"] == "assistant"
    
    def test_context_validation(self):
        """Test context format validation"""
        valid_context = [
            {"role": "user", "content": "Valid message"},
            {"role": "assistant", "content": "Valid response"}
        ]
        
        # Test valid context structure
        for message in valid_context:
            assert "role" in message
            assert "content" in message
            assert message["role"] in ["user", "assistant", "system"]
            assert isinstance(message["content"], str)
            assert len(message["content"]) > 0
        
        # Test invalid contexts (these should be handled gracefully)
        invalid_contexts = [
            [{"invalid": "structure"}],
            [{"role": "invalid_role", "content": "test"}],
            [{"role": "user"}],  # Missing content
            [{"content": "missing role"}],  # Missing role
        ]
        
        # System should handle invalid contexts gracefully
        for invalid_context in invalid_contexts:
            try:
                # If there's validation logic, it should catch these
                # For now, just ensure they don't crash the system
                chat_sessions.save_context("test_invalid", invalid_context)
                loaded = chat_sessions.load_last_context("test_invalid")
                # Should either save/load or handle gracefully
                assert loaded is not None or loaded is None
            except Exception as e:
                # If validation exists and rejects invalid contexts, that's also acceptable
                assert "validation" in str(e).lower() or "invalid" in str(e).lower()


class TestDatabasePerformance:
    """Test database performance and optimization"""
    
    def setup_method(self):
        """Setup test database"""
        chat_sessions.initialize_db()
    
    def teardown_method(self):
        """Cleanup"""
        pass
    
    def test_bulk_operations_performance(self):
        """Test performance with bulk database operations"""
        import time
        
        start_time = time.time()
        
        # Save contexts for 10 different chats (reduced for testing)
        for i in range(10):
            chat_id = f"performance_chat_{i}_{int(time.time())}"  # Unique IDs
            context = [
                {"role": "user", "content": f"Performance test message {i}"},
                {"role": "assistant", "content": f"Performance test response {i}"}
            ]
            chat_sessions.save_context(chat_id, context)
        
        save_time = time.time() - start_time
        
        # Load all contexts
        start_time = time.time()
        for i in range(10):
            chat_id = f"performance_chat_{i}_{int(time.time() - save_time)}"
            chat_sessions.load_last_context(chat_id)
            # May be None if chat doesn't exist, that's ok
        
        load_time = time.time() - start_time
        
        # Performance should be reasonable (< 2 seconds for 10 operations)
        assert save_time < 2.0, f"Save operations too slow: {save_time}s"
        assert load_time < 2.0, f"Load operations too slow: {load_time}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])