"""
☁️ WhatsApp Cloud API Provider
Integración con Meta WhatsApp Business Platform (Graph API)
"""

import logging
import os
from typing import Any, Optional

import requests

from src.services.audio_transcriber import audio_transcriber
from src.services.whatsapp_provider import MessageType, NormalizedMessage, SendResult, WhatsAppProvider

logger = logging.getLogger(__name__)


class CloudProvider(WhatsAppProvider):
    """Proveedor para WhatsApp Cloud API (Meta)"""

    def __init__(self):
        self.token = os.environ.get("WHATSAPP_CLOUD_TOKEN")
        self.phone_id = os.environ.get("WHATSAPP_PHONE_ID")
        self.api_version = os.environ.get("WHATSAPP_API_VERSION", "v18.0")
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_id}"

        if not self.token or not self.phone_id:
            logger.warning("⚠️ CloudProvider: WHATSAPP_CLOUD_TOKEN o WHATSAPP_PHONE_ID no configurados")
        else:
            logger.info("☁️ CloudProvider inicializado (Meta Graph API)")

    def send_message(self, chat_id: str, text: str, media: Optional[dict[str, Any]] = None) -> SendResult:
        """
        Enviar mensaje a través de Cloud API
        """
        if not self.token or not self.phone_id:
            return SendResult(success=False, error="Cloud API no configurado", provider="cloud")

        try:
            url = f"{self.base_url}/messages"
            headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

            # Construir payload según tipo de mensaje
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": chat_id,
            }

            if media:
                # Mensaje con media
                media_type = media.get("type", "image")
                payload["type"] = media_type
                payload[media_type] = {
                    "link": media.get("url") if media.get("url") else None,
                    "id": media.get("id") if media.get("id") else None,
                }
                if text:
                    payload[media_type]["caption"] = text
            else:
                # Mensaje de texto
                payload["type"] = "text"
                payload["text"] = {"body": text}

            response = requests.post(url, json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                message_id = data.get("messages", [{}])[0].get("id")

                logger.info(f"✅ Mensaje enviado via Cloud API: {message_id}")

                return SendResult(success=True, message_id=message_id, provider="cloud")
            else:
                error_msg = response.json().get("error", {}).get("message", response.text)
                logger.error(f"❌ Error Cloud API: {error_msg}")

                return SendResult(success=False, error=error_msg, provider="cloud")

        except Exception as e:
            logger.error(f"❌ Excepción enviando via Cloud API: {e}")
            return SendResult(success=False, error=str(e), provider="cloud")

    def receive_message(self, raw_event: dict[str, Any]) -> Optional[NormalizedMessage]:
        """
        Recibir y normalizar mensaje de Cloud API webhook
        """
        try:
            # Formato de webhook de Meta
            entry = raw_event.get("entry", [])[0]
            changes = entry.get("changes", [])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])

            if not messages:
                return None

            message = messages[0]

            # Extraer información
            chat_id = message.get("from")
            timestamp = message.get("timestamp")
            message_type = message.get("type", "text")

            # Texto del mensaje
            text = None
            media_url = None
            media_id = None

            if message_type == "text":
                text = message.get("text", {}).get("body")
            elif message_type == "image":
                media_id = message.get("image", {}).get("id")
                text = message.get("image", {}).get("caption")
            elif message_type == "audio":
                media_id = message.get("audio", {}).get("id")
                # Intentar transcribir audio
                if media_id:
                    audio_bytes = self.download_media(media_id)
                    if audio_bytes:
                        transcribed = audio_transcriber.transcribe(audio_bytes, language="es", audio_id=media_id)
                        if transcribed:
                            text = f"[Audio transcrito]: {transcribed}"
                            logger.info(f"🎤 Audio transcrito para {chat_id}")
            elif message_type == "video":
                media_id = message.get("video", {}).get("id")
                text = message.get("video", {}).get("caption")
            elif message_type == "document":
                media_id = message.get("document", {}).get("id")
                text = message.get("document", {}).get("caption")

            return NormalizedMessage(
                chat_id=chat_id,
                text=text,
                message_type=MessageType(message_type)
                if message_type in MessageType.__members__.values()
                else MessageType.TEXT,
                media_id=media_id,
                media_url=media_url,
                timestamp=timestamp,
                from_user=chat_id,
                metadata={"provider": "cloud", "raw_type": message_type},
            )

        except Exception as e:
            logger.error(f"❌ Error normalizando mensaje Cloud API: {e}")
            return None

    def download_media(self, media_id: str) -> Optional[bytes]:
        """
        Descargar media de Cloud API
        """
        if not self.token:
            logger.error("❌ Token no configurado para descargar media")
            return None

        try:
            # Paso 1: Obtener URL del media
            url = f"https://graph.facebook.com/{self.api_version}/{media_id}"
            headers = {"Authorization": f"Bearer {self.token}"}

            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                logger.error(f"❌ Error obteniendo URL de media: {response.text}")
                return None

            media_url = response.json().get("url")

            if not media_url:
                logger.error("❌ URL de media no encontrada")
                return None

            # Paso 2: Descargar el archivo
            media_response = requests.get(media_url, headers=headers, timeout=60)

            if media_response.status_code == 200:
                logger.info(f"✅ Media descargado: {media_id}")
                return media_response.content
            else:
                logger.error(f"❌ Error descargando media: {media_response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Excepción descargando media: {e}")
            return None

    def is_available(self) -> bool:
        """Verificar si Cloud API está disponible"""
        if not self.token or not self.phone_id:
            return False

        try:
            # Verificar conectividad con una petición simple
            url = f"https://graph.facebook.com/{self.api_version}/{self.phone_id}"
            headers = {"Authorization": f"Bearer {self.token}"}

            response = requests.get(url, headers=headers, timeout=10)
            return response.status_code == 200

        except Exception as e:
            logger.error(f"❌ Error verificando disponibilidad Cloud API: {e}")
            return False

    def get_status(self) -> dict[str, Any]:
        """Obtener estado del proveedor Cloud"""
        if not self.token or not self.phone_id:
            return {
                "provider": "cloud",
                "available": False,
                "error": "No configurado (falta token o phone_id)",
                "method": "Meta WhatsApp Business API",
            }

        is_avail = self.is_available()

        return {
            "provider": "cloud",
            "available": is_avail,
            "phone_id": self.phone_id,
            "api_version": self.api_version,
            "method": "Meta WhatsApp Business API",
            "features": ["Media oficial", "Webhooks", "Templates", "Audio transcription ready"],
        }


def verify_webhook(mode: str, token: str, challenge: str) -> Optional[str]:
    """
    Verificar webhook de Meta

    Args:
        mode: Debe ser 'subscribe'
        token: Token de verificación configurado
        challenge: Challenge string de Meta

    Returns:
        challenge si es válido, None si no
    """
    verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN")

    if not verify_token:
        logger.error("❌ WHATSAPP_VERIFY_TOKEN no configurado. Webhook rechazado.")
        return None

    if mode == "subscribe" and token == verify_token:
        logger.info("✅ Webhook verificado correctamente")
        return challenge
    else:
        logger.warning("⚠️ Verificación de webhook fallida")
        return None


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verificar la firma X-Hub-Signature-256 de Meta para validar
    que el webhook proviene de Meta y no ha sido manipulado.

    Args:
        payload: Cuerpo raw del request
        signature: Valor del header X-Hub-Signature-256

    Returns:
        True si la firma es válida
    """
    import hashlib
    import hmac

    app_secret = os.environ.get("WHATSAPP_APP_SECRET")
    if not app_secret:
        logger.warning("⚠️ WHATSAPP_APP_SECRET no configurado. No se puede verificar firma.")
        return False

    if not signature or not signature.startswith("sha256="):
        logger.warning("⚠️ Firma de webhook ausente o con formato inválido")
        return False

    expected_signature = "sha256=" + hmac.new(app_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected_signature, signature)
