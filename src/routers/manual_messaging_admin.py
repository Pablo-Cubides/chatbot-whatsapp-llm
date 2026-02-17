"""Manual messaging and media routes extracted from admin_panel."""

import json
import logging
import mimetypes
import os
import uuid
from datetime import datetime
from pathlib import PurePath
from typing import Any, Optional

import chat_sessions
import stub_chat
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.routers.whatsapp_runtime_admin import get_whatsapp_runtime_status
from src.services.audit_system import log_bulk_send
from src.services.auth_system import get_current_user, require_admin
from src.services.queue_system import queue_manager

router = APIRouter(tags=["manual-messaging-admin"])
logger = logging.getLogger(__name__)


class MessageComposeRequest(BaseModel):
    chat_id: str
    objective: str
    additional_context: Optional[str] = ""


class MessageSendRequest(BaseModel):
    chat_id: str
    message: str
    media: Optional[dict] = None  # {"fileId": str, "type": str}


class BulkMessageRequest(BaseModel):
    contacts: list[str]
    template: str
    objective: str
    media: Optional[dict] = None


@router.post("/api/settings/chat/toggle")
def api_toggle_chat(current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Toggle chat_enabled in data/settings.json."""
    settings_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "settings.json"))

    settings = {}
    if os.path.exists(settings_file):
        with open(settings_file, encoding="utf-8") as f:
            settings = json.load(f)

    settings["chat_enabled"] = not settings.get("chat_enabled", True)
    os.makedirs(os.path.dirname(settings_file), exist_ok=True)
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

    return {"chat_enabled": settings["chat_enabled"]}


@router.post("/api/automator/test-reply")
def api_test_reply(current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Test endpoint to verify LM Studio connection and reply generation."""
    try:
        test_message = "Hola, esto es una prueba"
        test_chat_id = "test_chat"
        test_history = []

        reply = stub_chat.chat(test_message, test_chat_id, test_history)

        return {
            "success": True,
            "test_message": test_message,
            "reply": reply,
            "message": "LM Studio connection and reply generation working",
        }
    except Exception as e:
        return {"success": False, "error": str(e), "message": "Error testing reply generation"}


@router.post("/api/chat/compose")
def api_compose_message(payload: MessageComposeRequest, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Generate a message using AI for a specific contact and objective."""
    try:
        compose_prompt = f"""Eres un asistente experto en comunicación. Tu tarea es generar un mensaje de WhatsApp profesional y personalizado.

OBJETIVO DEL MENSAJE: {payload.objective}

INFORMACIÓN ADICIONAL: {payload.additional_context if payload.additional_context else "Ninguna"}

INSTRUCCIONES:
1. Genera un mensaje claro, conciso y profesional
2. Adapta el tono según el objetivo (formal para citas médicas, amigable para recordatorios personales)
3. Incluye solo el texto del mensaje, sin explicaciones adicionales
4. Máximo 200 palabras
5. Evita usar emojis excesivos
6. Sé directo y específico

Genera ÚNICAMENTE el texto del mensaje:"""

        generated_message = stub_chat.chat(compose_prompt, payload.chat_id, [])
        if generated_message:
            return {"success": True, "reply": generated_message}
        return {"success": False, "error": "No se pudo generar el mensaje. Verifica que LM Studio esté funcionando."}
    except Exception as e:
        return {"success": False, "error": f"Error generando mensaje: {str(e)}"}


@router.post("/api/whatsapp/send")
def api_send_whatsapp_message(payload: MessageSendRequest, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Queue a message for WhatsApp automator."""
    try:
        status = get_whatsapp_runtime_status()
        if status.get("status") != "running":
            return {"success": False, "error": "WhatsApp automator no está ejecutándose"}

        try:
            metadata = {"source": "manual_admin"}
            if payload.media:
                metadata["media"] = payload.media

            queue_manager.enqueue_message(
                chat_id=payload.chat_id,
                message=payload.message,
                when=None,
                priority=1,
                metadata=metadata,
            )

            logging.info("Queued manual message to %s: %s", payload.chat_id, payload.message)
        except Exception as e:
            logging.error("Error queuing manual message: %s", e)
            return {"success": False, "error": f"Error al programar mensaje: {str(e)}"}

        try:
            history = chat_sessions.load_last_context(payload.chat_id) or []
            history_entry = {"role": "assistant", "content": payload.message, "manual": True}
            if payload.media:
                history_entry["media"] = json.dumps(payload.media)
            history.append(history_entry)
            chat_sessions.save_context(payload.chat_id, history)
        except Exception as e:
            logger.warning("Error saving manual message to history: %s", e)

        media_text = " con archivo multimedia" if payload.media else ""
        return {
            "success": True,
            "message": f"Mensaje{media_text} enviado a cola para {payload.chat_id}",
            "note": "El mensaje ha sido programado y será enviado por el automator de WhatsApp.",
        }
    except Exception as e:
        return {"success": False, "error": f"Error enviando mensaje: {str(e)}"}


@router.post("/api/whatsapp/bulk-send")
async def api_bulk_send_messages(payload: BulkMessageRequest, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Create a campaign and enqueue bulk messages."""
    try:
        campaign_id = queue_manager.create_campaign(
            name=f"Bulk {payload.objective[:50]}",
            created_by=current_user.get("username", "unknown"),
            total_messages=len(payload.contacts),
            metadata={"objective": payload.objective, "template": payload.template},
        )

        results = []
        for contact_number in payload.contacts:
            try:
                compose_prompt = f"""Eres un asistente experto en comunicación. Genera contenido personalizado basado en el objetivo.

OBJETIVO: {payload.objective}
CONTACTO: {contact_number}

INSTRUCCIONES:
1. Genera contenido específico y personalizado
2. Mantén un tono profesional y amigable
3. Sé conciso y directo
4. Máximo 150 palabras
5. Solo proporciona el contenido, sin explicaciones adicionales

Genera el contenido personalizado:"""

                personalized_content = stub_chat.chat(compose_prompt, contact_number, [])
                final_message = (
                    payload.template.replace("{custom}", personalized_content)
                    if personalized_content
                    else payload.template.replace("{custom}", "contenido personalizado")
                )

                message_id = queue_manager.enqueue_message(
                    chat_id=contact_number,
                    message=final_message,
                    priority=0,
                    metadata={"campaign_id": campaign_id, "bulk": True, "objective": payload.objective},
                )

                try:
                    history = chat_sessions.load_last_context(contact_number) or []
                    history.append(
                        {
                            "role": "assistant",
                            "content": final_message,
                            "bulk": True,
                            "campaign_id": campaign_id,
                        }
                    )
                    chat_sessions.save_context(contact_number, history)
                except Exception as e:
                    logger.warning("Error saving bulk message to history for %s: %s", contact_number, e)

                results.append(
                    {"contact": contact_number, "success": True, "message_id": message_id, "message": final_message}
                )
            except Exception as e:
                results.append(
                    {
                        "contact": contact_number,
                        "success": False,
                        "error": f"Error procesando mensaje para {contact_number}: {str(e)}",
                    }
                )

        successful_sends = sum(1 for r in results if r["success"])
        total_contacts = len(payload.contacts)

        log_bulk_send(
            current_user.get("username", "unknown"),
            current_user.get("role", "unknown"),
            campaign_id,
            total_contacts,
            {"objective": payload.objective, "successful": successful_sends},
        )

        return {
            "success": True,
            "campaign_id": campaign_id,
            "total": total_contacts,
            "successful": successful_sends,
            "failed": total_contacts - successful_sends,
            "results": results,
            "message": f"Campaña creada. {successful_sends}/{total_contacts} mensajes encolados correctamente.",
        }
    except Exception as e:
        return {"success": False, "error": f"Error en bulk send: {str(e)}"}


@router.post("/api/media/upload")
async def upload_media_file(
    file: UploadFile = File(...), messageType: str = "manual", current_user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    """Upload media file for message attachments."""
    try:
        allowed_message_types = {"manual", "bulk"}
        if messageType not in allowed_message_types:
            raise HTTPException(status_code=400, detail="messageType inválido")

        allowed_types = [
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "video/mp4",
            "video/avi",
            "video/mov",
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ]

        allowed_extensions = {
            "image/jpeg": {".jpg", ".jpeg"},
            "image/png": {".png"},
            "image/gif": {".gif"},
            "image/webp": {".webp"},
            "video/mp4": {".mp4"},
            "video/avi": {".avi"},
            "video/mov": {".mov"},
            "application/pdf": {".pdf"},
            "application/msword": {".doc"},
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
            "application/vnd.ms-excel": {".xls"},
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {".xlsx"},
        }

        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Tipo de archivo no permitido: {file.content_type}")

        if not file.filename:
            raise HTTPException(status_code=400, detail="Nombre de archivo requerido")

        sanitized_filename = PurePath(file.filename).name
        file_extension = os.path.splitext(sanitized_filename)[1].lower()
        if not file_extension:
            guessed_ext = mimetypes.guess_extension(file.content_type or "")
            file_extension = (guessed_ext or "").lower()

        expected_extensions = allowed_extensions.get(file.content_type or "", set())
        if expected_extensions and file_extension not in expected_extensions:
            raise HTTPException(status_code=400, detail="Extensión de archivo no coincide con el tipo MIME")

        max_size = 25 * 1024 * 1024
        contents = await file.read()
        if len(contents) > max_size:
            raise HTTPException(status_code=413, detail="Archivo muy grande. Máximo 25MB permitido")

        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        media_dir = os.path.join(root, "media_uploads")
        os.makedirs(media_dir, exist_ok=True)

        unique_filename = f"{messageType}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{file_extension}"
        file_path = os.path.join(media_dir, unique_filename)

        with open(file_path, "wb") as f:
            f.write(contents)

        file_info = {
            "fileId": unique_filename,
            "originalName": sanitized_filename,
            "contentType": file.content_type,
            "size": len(contents),
            "messageType": messageType,
            "uploadTime": datetime.now().isoformat(),
        }
        logging.info("Media file uploaded: %s", file_info)

        return {"success": True, "fileId": unique_filename, "originalName": sanitized_filename, "size": len(contents)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error subiendo archivo: {str(e)}")
