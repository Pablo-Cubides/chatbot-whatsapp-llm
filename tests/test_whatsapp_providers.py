"""
Tests para los providers de WhatsApp
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.services.whatsapp_provider import (
    DualProvider,
    NormalizedMessage,
    SendResult,
    WhatsAppProvider,
    WhatsAppProviderFactory,
)


class TestWhatsAppProviderFactory:
    def test_create_web_provider(self):
        """Test crear provider Web"""
        with patch.dict(os.environ, {"WHATSAPP_MODE": "web"}):
            provider = WhatsAppProviderFactory.create_from_env()

            assert provider is not None
            assert provider.__class__.__name__ in ["WebProvider", "DualProvider"]

    def test_create_cloud_provider(self):
        """Test crear provider Cloud"""
        with patch.dict(
            os.environ, {"WHATSAPP_MODE": "cloud", "WHATSAPP_CLOUD_TOKEN": "test_token", "WHATSAPP_PHONE_ID": "test_phone_id"}
        ):
            provider = WhatsAppProviderFactory.create_from_env()

            assert provider is not None

    def test_create_dual_provider(self):
        """Test crear DualProvider (ambos modos)"""
        with patch.dict(
            os.environ, {"WHATSAPP_MODE": "both", "WHATSAPP_CLOUD_TOKEN": "test_token", "WHATSAPP_PHONE_ID": "test_phone_id"}
        ):
            provider = WhatsAppProviderFactory.create_from_env()

            # create_from_env returns CloudProvider for 'both' mode
            # DualProvider is created by get_provider() instead
            assert provider is not None


class TestDualProvider:
    def setup_method(self):
        """Setup para cada test"""
        self.mock_primary = MagicMock(spec=WhatsAppProvider)
        self.mock_backup = MagicMock(spec=WhatsAppProvider)

        with (
            patch("src.services.whatsapp_cloud_provider.CloudProvider", return_value=self.mock_primary),
            patch("src.services.whatsapp_web_provider.WebProvider", return_value=self.mock_backup),
        ):
            self.dual_provider = DualProvider()

    def test_send_message_primary_success(self):
        """Test envío exitoso con provider primario"""
        self.mock_primary.send_message.return_value = SendResult(success=True, message_id="msg_123", provider="cloud")
        self.mock_primary.is_available.return_value = True

        result = self.dual_provider.send_message(chat_id="1234567890", text="Test message")

        assert result.success is True

    def test_send_message_fallback_to_backup(self):
        """Test fallback a backup cuando primario falla"""
        self.mock_primary.is_available.return_value = False
        self.mock_backup.is_available.return_value = True
        self.mock_backup.send_message.return_value = SendResult(success=True, message_id="msg_backup_456", provider="web")

        result = self.dual_provider.send_message(chat_id="1234567890", text="Test message")

        assert result.success is True
        self.mock_backup.send_message.assert_called_once()

    def test_send_message_both_fail(self):
        """Test cuando ambos providers fallan"""
        self.mock_primary.is_available.return_value = False
        self.mock_backup.is_available.return_value = False
        self.mock_backup.send_message.return_value = SendResult(success=False, error="No disponible", provider="web")

        result = self.dual_provider.send_message(chat_id="1234567890", text="Test message")

        assert result.success is False

    def test_is_available_both(self):
        """Test disponibilidad cuando ambos están disponibles"""
        self.mock_primary.is_available.return_value = True
        self.mock_backup.is_available.return_value = True

        assert self.dual_provider.is_available() is True

    def test_is_available_one(self):
        """Test disponibilidad cuando solo uno está disponible"""
        self.mock_primary.is_available.return_value = False
        self.mock_backup.is_available.return_value = True

        assert self.dual_provider.is_available() is True

    def test_is_available_none(self):
        """Test disponibilidad cuando ninguno está disponible"""
        self.mock_primary.is_available.return_value = False
        self.mock_backup.is_available.return_value = False

        assert self.dual_provider.is_available() is False

    def test_get_status(self):
        """Test obtener estado de ambos providers"""
        self.mock_primary.get_status.return_value = {"provider": "cloud", "available": True}
        self.mock_backup.get_status.return_value = {"provider": "web", "available": False}

        status = self.dual_provider.get_status()

        assert "primary" in status
        assert "backup" in status


class TestNormalizedMessage:
    def test_create_normalized_message(self):
        """Test crear mensaje normalizado"""
        msg = NormalizedMessage(
            chat_id="chat_456",
            text="Test message",
            timestamp="2024-01-01 12:00:00",
            from_user="Test User",
        )

        assert msg.chat_id == "chat_456"
        assert msg.text == "Test message"

    def test_normalized_message_optional_fields(self):
        """Test mensaje con campos opcionales"""
        msg = NormalizedMessage(
            chat_id="chat_456",
            text="Test",
            timestamp="2024-01-01 12:00:00",
            media_url="https://example.com/audio.ogg",
        )

        assert msg.media_url == "https://example.com/audio.ogg"


class TestSendResult:
    def test_send_result_success(self):
        """Test resultado exitoso"""
        result = SendResult(success=True, message_id="msg_123", provider="cloud")

        assert result.success is True
        assert result.message_id == "msg_123"
        assert result.error is None

    def test_send_result_failure(self):
        """Test resultado con error"""
        result = SendResult(success=False, provider="cloud", error="Connection timeout")

        assert result.success is False
        assert result.message_id is None
        assert result.error == "Connection timeout"


if __name__ == "__main__":
    pytest.main([__file__])
