"""
Tests para el sistema de cola de mensajes
"""

import pytest

from src.models.admin_db import engine
from src.models.models import Base
from src.services.queue_system import QueueManager

pytestmark = pytest.mark.unit


class TestQueueSystem:
    @classmethod
    def setup_class(cls):
        """Setup una vez para toda la clase - crear tablas"""
        Base.metadata.create_all(bind=engine)

    def setup_method(self):
        """Setup para cada test"""
        self.queue_manager = QueueManager()

    @classmethod
    def teardown_class(cls):
        """Cleanup después de todos los tests"""
        # Opcionalmente borrar tablas después de tests
        # Base.metadata.drop_all(bind=engine)
        pass

    def test_enqueue_message(self):
        """Test encolar mensaje básico"""
        message_id = self.queue_manager.enqueue_message(chat_id="1234567890", message="Test message", priority=1)

        assert message_id is not None
        assert message_id.startswith("msg_")

    def test_enqueue_with_metadata(self):
        """Test encolar con metadata"""
        metadata = {"campaign_id": "camp_123", "custom_field": "value"}

        message_id = self.queue_manager.enqueue_message(chat_id="1234567890", message="Test with metadata", metadata=metadata)

        assert message_id is not None

    def test_get_pending_messages(self):
        """Test obtener mensajes pendientes"""
        # Encolar algunos mensajes
        self.queue_manager.enqueue_message("chat_pending_1", "Message 1")
        self.queue_manager.enqueue_message("chat_pending_2", "Message 2")

        pending = self.queue_manager.get_pending_messages(limit=1000)

        assert isinstance(pending, list)
        assert len(pending) >= 2

        chat_ids = {msg["chat_id"] for msg in pending}
        assert "chat_pending_1" in chat_ids
        assert "chat_pending_2" in chat_ids

    @pytest.mark.parametrize(
        ("operation", "args"),
        [
            ("mark_as_sent", tuple()),
            ("mark_as_failed", ("Test error",)),
        ],
    )
    def test_message_status_transitions(self, operation, args):
        """Test marcar mensajes en distintos estados finales."""
        message_id = self.queue_manager.enqueue_message("chat1", "Test")
        method = getattr(self.queue_manager, operation)
        result = method(message_id, *args)
        assert result is True

    def test_create_campaign(self):
        """Test crear campaña"""
        campaign_id = self.queue_manager.create_campaign(name="Test Campaign", created_by="test_user", total_messages=10)

        assert campaign_id is not None
        assert campaign_id.startswith("camp_")

    def test_get_campaign_status(self):
        """Test obtener estado de campaña"""
        campaign_id = self.queue_manager.create_campaign(name="Test Campaign", created_by="test_user", total_messages=5)

        status = self.queue_manager.get_campaign_status(campaign_id)

        assert status is not None
        assert status["campaign_id"] == campaign_id
        assert status["total_messages"] == 5

    def test_pause_resume_campaign(self):
        """Test pausar y reanudar campaña"""
        campaign_id = self.queue_manager.create_campaign(name="Test Campaign", created_by="test_user", total_messages=3)

        # Pausar
        result = self.queue_manager.pause_campaign(campaign_id)
        assert result is True

        status = self.queue_manager.get_campaign_status(campaign_id)
        assert status["status"] == "paused"

        # Reanudar
        result = self.queue_manager.resume_campaign(campaign_id)
        assert result is True

        status = self.queue_manager.get_campaign_status(campaign_id)
        assert status["status"] == "active"

    def test_cancel_campaign(self):
        """Test cancelar campaña"""
        campaign_id = self.queue_manager.create_campaign(name="Test Campaign", created_by="test_user", total_messages=3)

        result = self.queue_manager.cancel_campaign(campaign_id)

        assert result is True


if __name__ == "__main__":
    pytest.main([__file__])
