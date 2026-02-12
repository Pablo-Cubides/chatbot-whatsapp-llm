"""
WhatsApp Cloud API Webhooks Router.
Extracted from admin_panel.py — handles webhook verification and message reception.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from src.routers.deps import (
    alert_manager,
    get_current_user,
    get_provider,
    verify_webhook,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


@router.get("/webhooks/whatsapp")
async def whatsapp_webhook_verify(request: Request):
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
async def whatsapp_webhook_receive(request: Request):
    """Recepción de mensajes de WhatsApp Cloud API"""
    try:
        body = await request.json()

        provider = get_provider()

        normalized_msg = provider.receive_message(body)

        if not normalized_msg:
            return {"status": "ok", "message": "No processable message"}

        logger.info(f"📨 Mensaje recibido via Cloud API de {normalized_msg.chat_id}")

        if normalized_msg.text:
            alert_manager.check_alert_rules(
                normalized_msg.text,
                normalized_msg.chat_id,
                {"provider": "cloud"},
            )

        # TODO: Integrate with stub_chat or the response pipeline
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"❌ Error procesando webhook de WhatsApp: {e}")
        # Return 200 so Meta doesn't retry
        return {"status": "error", "message": str(e)}


@router.get("/api/whatsapp/provider/status")
async def get_whatsapp_provider_status(
    current_user: dict[str, Any] = Depends(get_current_user),
):
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
