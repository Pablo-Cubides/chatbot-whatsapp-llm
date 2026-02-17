"""
WhatsApp Cloud API Webhooks Router.
Extracted from admin_panel.py — handles webhook verification and message reception.
"""

import json
import logging
from importlib import import_module
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from src.services.alert_system import alert_manager
from src.services.auth_system import get_current_user
from src.services.whatsapp_cloud_provider import verify_webhook, verify_webhook_signature
from src.services.whatsapp_provider import get_provider

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


@router.get("/webhooks/whatsapp")
async def whatsapp_webhook_verify(request: Request) -> JSONResponse:
    """Verificación de webhook de WhatsApp Cloud API"""
    try:
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if not mode or not token:
            raise HTTPException(status_code=400, detail="Missing parameters")

        verified_challenge = verify_webhook(mode, token, challenge)

        if verified_challenge:
            return JSONResponse(content=int(verified_challenge), media_type="text/plain")
        else:
            raise HTTPException(status_code=403, detail="Verification failed")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en verificación de webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook_receive(request: Request) -> dict[str, str]:
    """Recepción de mensajes de WhatsApp Cloud API"""
    try:
        raw_body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256", "")
        is_valid = await run_in_threadpool(verify_webhook_signature, raw_body, signature)
        if not is_valid:
            logger.warning("❌ Firma de webhook inválida")
            return JSONResponse(status_code=403, content={"status": "error", "message": "Invalid signature"})

        body = json.loads(raw_body.decode("utf-8") or "{}")

        provider = get_provider()

        normalized_msg = await run_in_threadpool(provider.receive_message, body)

        if not normalized_msg:
            return {"status": "ok", "message": "No processable message"}

        logger.info(f"📨 Mensaje recibido via Cloud API de {normalized_msg.chat_id}")

        if normalized_msg.text:
            await run_in_threadpool(
                alert_manager.check_alert_rules,
                normalized_msg.text,
                normalized_msg.chat_id,
                {"provider": "cloud"},
            )

            try:
                stub_chat_module = import_module("stub_chat")
                chat_sessions_module = import_module("chat_sessions")

                history = await run_in_threadpool(chat_sessions_module.load_last_context, normalized_msg.chat_id)
                history = history or []

                reply = await run_in_threadpool(stub_chat_module.chat, normalized_msg.text, normalized_msg.chat_id, history)

                if reply:
                    history.append({"role": "user", "content": normalized_msg.text})
                    history.append({"role": "assistant", "content": reply})
                    await run_in_threadpool(chat_sessions_module.save_context, normalized_msg.chat_id, history)

                    send_result = await run_in_threadpool(provider.send_message, normalized_msg.chat_id, reply)
                    if not send_result.success:
                        logger.error("❌ Error enviando respuesta webhook: %s", send_result.error)
            except ModuleNotFoundError:
                logger.warning("⚠️ Módulos de pipeline no disponibles, se omite auto-respuesta")
            except Exception as pipeline_error:
                logger.error("❌ Error en pipeline de respuesta webhook: %s", pipeline_error)

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"❌ Error procesando webhook de WhatsApp: {e}")
        # Return 200 so Meta doesn't retry
        return {"status": "error", "message": str(e)}


@router.get("/api/whatsapp/provider/status")
async def get_whatsapp_provider_status(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Obtener estado del proveedor de WhatsApp actual"""
    try:
        import os

        provider = get_provider()
        status = provider.get_status()

        mode = os.environ.get("WHATSAPP_MODE", "web")

        return {
            "mode": mode,
            "status": status,
            "available": provider.is_available(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
