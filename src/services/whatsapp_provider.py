"""
📱 WhatsApp Provider - Abstracción unificada para Web y Cloud API
Soporta múltiples proveedores de WhatsApp de forma intercambiable
"""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ProviderType(str, Enum):
    """Tipos de proveedor"""

    WEB = "web"
    CLOUD = "cloud"


class MessageType(str, Enum):
    """Tipos de mensaje"""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"


@dataclass
class NormalizedMessage:
    """Mensaje normalizado independiente del proveedor"""

    chat_id: str
    text: Optional[str] = None
    message_type: MessageType = MessageType.TEXT
    media_url: Optional[str] = None
    media_id: Optional[str] = None
    timestamp: Optional[str] = None
    from_user: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


@dataclass
class SendResult:
    """Resultado de envío de mensaje"""

    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    provider: Optional[str] = None


class WhatsAppProvider(ABC):
    """Interfaz abstracta para proveedores de WhatsApp"""

    @abstractmethod
    def send_message(self, chat_id: str, text: str, media: Optional[dict[str, Any]] = None) -> SendResult:
        """
        Enviar mensaje

        Args:
            chat_id: ID del chat destino
            text: Texto del mensaje
            media: Información de media (opcional)

        Returns:
            SendResult con resultado del envío
        """
        pass

    @abstractmethod
    def receive_message(self, raw_event: dict[str, Any]) -> Optional[NormalizedMessage]:
        """
        Recibir y normalizar mensaje

        Args:
            raw_event: Evento crudo del proveedor

        Returns:
            NormalizedMessage normalizado o None si no es válido
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Verificar si el proveedor está disponible"""
        pass

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """Obtener estado del proveedor"""
        pass


class WhatsAppProviderFactory:
    """Factory para crear proveedores según configuración"""

    @staticmethod
    def create_provider(provider_type: str) -> WhatsAppProvider:
        """
        Crear proveedor según tipo

        Args:
            provider_type: 'web' o 'cloud'

        Returns:
            Instancia del proveedor correspondiente
        """
        if provider_type == ProviderType.WEB:
            from src.services.whatsapp_web_provider import WebProvider

            return WebProvider()
        elif provider_type == ProviderType.CLOUD:
            from src.services.whatsapp_cloud_provider import CloudProvider

            return CloudProvider()
        else:
            raise ValueError(f"Tipo de proveedor desconocido: {provider_type}")

    @staticmethod
    def create_from_env() -> WhatsAppProvider:
        """Crear proveedor desde variables de entorno"""
        mode = os.environ.get("WHATSAPP_MODE", "web").lower()

        if mode == "both":
            # Para modo dual, retornar el cloud como principal
            logger.info("📱 Modo DUAL activado: Cloud API principal, Web como backup")
            return WhatsAppProviderFactory.create_provider(ProviderType.CLOUD)
        else:
            logger.info(f"📱 Proveedor WhatsApp: {mode}")
            return WhatsAppProviderFactory.create_provider(mode)


class DualProvider(WhatsAppProvider):
    """
    Proveedor dual que usa Cloud API como principal y Web como backup
    """

    def __init__(self):
        from src.services.whatsapp_cloud_provider import CloudProvider
        from src.services.whatsapp_web_provider import WebProvider

        self.primary = CloudProvider()
        self.backup = WebProvider()
        self.use_backup_for: set = set()  # Set de chat_ids que deben usar backup (bounded)
        self._max_backup_entries = 1000  # Prevent unbounded growth

        logger.info("📱 DualProvider inicializado (Cloud principal, Web backup)")

    def send_message(self, chat_id: str, text: str, media: Optional[dict[str, Any]] = None) -> SendResult:
        """Enviar mensaje usando primary o backup según disponibilidad"""

        # Si este chat está marcado para usar backup, ir directo ahí
        if chat_id in self.use_backup_for:
            result = self.backup.send_message(chat_id, text, media)
            result.provider = "web (backup)"
            return result

        # Intentar con primary
        if self.primary.is_available():
            result = self.primary.send_message(chat_id, text, media)

            if result.success:
                result.provider = "cloud (primary)"
                return result

            # Si falla, marcar para usar backup (con límite)
            logger.warning(f"⚠️ Cloud API falló para {chat_id}, usando Web backup")
            if len(self.use_backup_for) >= self._max_backup_entries:
                # If too many entries, clear old ones - primary may have recovered
                self.use_backup_for.clear()
                logger.info("🔄 Limpiado use_backup_for por exceder límite")
            self.use_backup_for.add(chat_id)

        # Fallback a backup
        result = self.backup.send_message(chat_id, text, media)
        result.provider = "web (backup)"
        return result

    def receive_message(self, raw_event: dict[str, Any]) -> Optional[NormalizedMessage]:
        """Recibir mensaje (auto-detect el proveedor)"""
        # Intentar parsear como Cloud API primero
        if "entry" in raw_event:  # Cloud API format
            return self.primary.receive_message(raw_event)
        else:  # Asumir Web format
            return self.backup.receive_message(raw_event)

    def is_available(self) -> bool:
        """Disponible si al menos uno de los dos está disponible"""
        return self.primary.is_available() or self.backup.is_available()

    def get_status(self) -> dict[str, Any]:
        """Estado de ambos proveedores"""
        return {
            "mode": "dual",
            "primary": self.primary.get_status(),
            "backup": self.backup.get_status(),
            "chats_using_backup": len(self.use_backup_for),
        }


# Instancia global del router
_current_provider: Optional[WhatsAppProvider] = None


def get_provider() -> WhatsAppProvider:
    """Obtener instancia global del proveedor"""
    global _current_provider

    if _current_provider is None:
        mode = os.environ.get("WHATSAPP_MODE", "web").lower()

        _current_provider = DualProvider() if mode == "both" else WhatsAppProviderFactory.create_from_env()

    return _current_provider


def send_message(chat_id: str, text: str, media: Optional[dict[str, Any]] = None) -> SendResult:
    """Helper function para enviar mensaje usando el proveedor configurado"""
    provider = get_provider()
    return provider.send_message(chat_id, text, media)
