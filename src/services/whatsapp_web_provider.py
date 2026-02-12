"""
🌐 WhatsApp Web Provider
Wrapper para whatsapp_automator.py usando Playwright
"""

import json
import logging
import os
from typing import Any, Optional

from src.services.queue_system import queue_manager
from src.services.whatsapp_provider import MessageType, NormalizedMessage, SendResult, WhatsAppProvider

logger = logging.getLogger(__name__)


class WebProvider(WhatsAppProvider):
    """Proveedor para WhatsApp Web via Playwright"""

    def __init__(self):
        self.queue_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "manual_queue.json"
        )
        logger.info("🌐 WebProvider inicializado (Playwright)")

    def send_message(self, chat_id: str, text: str, media: Optional[dict[str, Any]] = None) -> SendResult:
        """
        Enviar mensaje a través de WhatsApp Web
        Encola el mensaje para que whatsapp_automator.py lo procese
        """
        try:
            # Encolar mensaje para que el automator lo procese
            message_id = queue_manager.enqueue_message(
                chat_id=chat_id, message=text, metadata={"provider": "web", "media": media}
            )

            return SendResult(success=True, message_id=message_id, provider="web")

        except Exception as e:
            logger.error(f"❌ Error enviando mensaje via Web: {e}")
            return SendResult(success=False, error=str(e), provider="web")

    def receive_message(self, raw_event: dict[str, Any]) -> Optional[NormalizedMessage]:
        """
        Recibir mensaje de WhatsApp Web
        El formato viene de whatsapp_automator.py
        """
        try:
            return NormalizedMessage(
                chat_id=raw_event.get("chat_id"),
                text=raw_event.get("text"),
                message_type=MessageType.TEXT,  # WhatsApp Web principalmente texto
                timestamp=raw_event.get("timestamp"),
                from_user=raw_event.get("from_user"),
                metadata={"provider": "web"},
            )
        except Exception as e:
            logger.error(f"❌ Error normalizando mensaje Web: {e}")
            return None

    def is_available(self) -> bool:
        """
        Verificar si WhatsApp Web está disponible
        Comprueba si el proceso whatsapp_automator está corriendo
        """
        try:
            # Verificar si existe el archivo de status
            status_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "status.json")

            if os.path.exists(status_file):
                with open(status_file) as f:
                    status = json.load(f)
                    return status.get("running", False)

            return False

        except Exception as e:
            logger.error(f"❌ Error verificando disponibilidad Web: {e}")
            return False

    def get_status(self) -> dict[str, Any]:
        """Obtener estado del proveedor Web"""
        try:
            status_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "status.json")

            if os.path.exists(status_file):
                with open(status_file) as f:
                    status = json.load(f)
                    return {
                        "provider": "web",
                        "available": status.get("running", False),
                        "connected": status.get("connected", False),
                        "last_check": status.get("timestamp"),
                        "method": "Playwright + WhatsApp Web",
                    }

            return {
                "provider": "web",
                "available": False,
                "error": "Status file not found",
                "method": "Playwright + WhatsApp Web",
            }

        except Exception as e:
            return {"provider": "web", "available": False, "error": str(e), "method": "Playwright + WhatsApp Web"}
