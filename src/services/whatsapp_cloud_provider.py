"""
☁️ WhatsApp Cloud API Provider
Integración con Meta WhatsApp Business Platform (Graph API)
"""

import logging
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

import httpx

from src.services.audio_transcriber import audio_transcriber
from src.services.whatsapp_provider import MessageType, NormalizedMessage, SendResult, WhatsAppProvider

logger = logging.getLogger(__name__)


def _run_async_blocking(coro):
    try:
        asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro)).result()
    except RuntimeError:
        return asyncio.run(coro)


async def _request_json_async(
    method: str,
    url: str,
    headers: Optional[dict[str, str]] = None,
    payload: Optional[dict[str, Any]] = None,
    timeout_seconds: float = 30,
) -> tuple[int, Any, str]:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.request(method, url, headers=headers, json=payload)
        text = response.text
        try:
            data = response.json()
        except Exception:
            data = None
        return response.status_code, data, text


async def _request_bytes_async(url: str, headers: Optional[dict[str, str]] = None, timeout_seconds: float = 60) -> tuple[int, bytes, str]:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.get(url, headers=headers)
        return response.status_code, response.content, response.text


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

            status_code, data, raw_text = _run_async_blocking(
                _request_json_async("POST", url, headers=headers, payload=payload, timeout_seconds=30)
            )

            if status_code == 200:
                data = data or {}
                message_id = data.get("messages", [{}])[0].get("id")

                logger.info("✅ Mensaje enviado via Cloud API: %s", message_id)

                return SendResult(success=True, message_id=message_id, provider="cloud")
            else:
                error_msg = (data or {}).get("error", {}).get("message", raw_text)
                logger.error("❌ Error Cloud API: %s", error_msg)

                return SendResult(success=False, error=error_msg, provider="cloud")

        except Exception as e:
            logger.error("❌ Excepción enviando via Cloud API: %s", e)
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
                            logger.info("🎤 Audio transcrito para %s", chat_id)
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
            logger.error("❌ Error normalizando mensaje Cloud API: %s", e)
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

            meta_status, meta_data, meta_text = _run_async_blocking(
                _request_json_async("GET", url, headers=headers, timeout_seconds=30)
            )

            if meta_status != 200:
                logger.error("❌ Error obteniendo URL de media: %s", meta_text)
                return None

            media_url = (meta_data or {}).get("url")

            if not media_url:
                logger.error("❌ URL de media no encontrada")
                return None

            # Paso 2: Descargar el archivo
            media_status, media_content, media_text = _run_async_blocking(
                _request_bytes_async(media_url, headers=headers, timeout_seconds=60)
            )

            if media_status == 200:
                logger.info("✅ Media descargado: %s", media_id)
                return media_content
            else:
                logger.error("❌ Error descargando media: %s", media_text)
                return None

        except Exception as e:
            logger.error("❌ Excepción descargando media: %s", e)
            return None

    def is_available(self) -> bool:
        """Verificar si Cloud API está disponible"""
        if not self.token or not self.phone_id:
            return False

        try:
            # Verificar conectividad con una petición simple
            url = f"https://graph.facebook.com/{self.api_version}/{self.phone_id}"
            headers = {"Authorization": f"Bearer {self.token}"}

            status_code, _data, _text = _run_async_blocking(_request_json_async("GET", url, headers=headers, timeout_seconds=10))
            return status_code == 200

        except Exception as e:
            logger.error("❌ Error verificando disponibilidad Cloud API: %s", e)
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
