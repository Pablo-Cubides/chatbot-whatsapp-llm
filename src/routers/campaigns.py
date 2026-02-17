"""
Campaign Management API Router — Bulk messaging campaigns.
Extracted from admin_panel.py.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.routers.deps import (
    get_current_user,
    log_bulk_send,
    queue_manager,
    require_admin,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


class CampaignCreate(BaseModel):
    name: str
    template: str
    contacts: list[str]  # List of phone numbers
    scheduled_at: Optional[str] = None  # ISO datetime or None for immediate
    delay_between_messages: Optional[int] = 5  # seconds


@router.get("")
async def list_campaigns(
    status: Optional[str] = None,
    limit: int = 50,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Listar todas las campañas"""
    try:
        campaigns = queue_manager.list_campaigns(status=status, limit=limit)
        return campaigns
    except Exception as e:
        logger.error(f"Error listando campañas: {e}")
        return []


@router.post("")
async def create_campaign(
    campaign: CampaignCreate,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Crear una nueva campaña de mensajes masivos"""
    try:
        if not campaign.name or not campaign.template:
            raise HTTPException(status_code=400, detail="Nombre y template son requeridos")

        if not campaign.contacts or len(campaign.contacts) == 0:
            raise HTTPException(
                status_code=400,
                detail="Se requiere al menos un contacto",
            )

        scheduled_base: Optional[datetime] = None
        if campaign.scheduled_at:
            parsed = campaign.scheduled_at.replace("Z", "+00:00")
            scheduled_base = datetime.fromisoformat(parsed)
            if scheduled_base.tzinfo is None:
                scheduled_base = scheduled_base.replace(tzinfo=timezone.utc)

        campaign_id = queue_manager.create_campaign(
            name=campaign.name,
            created_by=current_user.get("username", "admin"),
            total_messages=len(campaign.contacts),
            metadata={
                "template": campaign.template,
                "scheduled_at": campaign.scheduled_at,
                "delay_between_messages": campaign.delay_between_messages or 5,
            },
        )

        delay_seconds = campaign.delay_between_messages or 5
        bulk_rows: list[dict[str, Any]] = []
        for index, contact in enumerate(campaign.contacts):
            send_at = None
            if scheduled_base is not None:
                send_at = scheduled_base + timedelta(seconds=delay_seconds * index)

            bulk_rows.append(
                {
                    "chat_id": contact,
                    "message": campaign.template,
                    "when": send_at,
                    "priority": 0,
                    "metadata": {
                        "campaign_id": campaign_id,
                        "campaign_name": campaign.name,
                    },
                }
            )

        queued_ids = queue_manager.enqueue_bulk_messages(bulk_rows)
        if len(queued_ids) != len(campaign.contacts):
            raise HTTPException(status_code=500, detail="Error encolando campaña masiva")

        if campaign_id:
            log_bulk_send(
                current_user.get("username", "admin"),
                current_user.get("role", "admin"),
                campaign_id,
                len(campaign.contacts),
            )

            return {
                "success": True,
                "campaign_id": campaign_id,
                "message": (f"Campaña '{campaign.name}' creada con {len(campaign.contacts)} contactos"),
                "total_messages": len(campaign.contacts),
            }
        else:
            raise HTTPException(status_code=500, detail="Error creando campaña")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error creando campaña")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}")
async def get_campaign_status(
    campaign_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Obtener estado de una campaña"""
    try:
        status = queue_manager.get_campaign_status(campaign_id)
        if not status:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Pausar una campaña"""
    try:
        success = queue_manager.pause_campaign(campaign_id)
        if not success:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
        return {"success": True, "message": f"Campaña {campaign_id} pausada"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{campaign_id}/resume")
async def resume_campaign(
    campaign_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Reanudar una campaña"""
    try:
        success = queue_manager.resume_campaign(campaign_id)
        if not success:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
        return {
            "success": True,
            "message": f"Campaña {campaign_id} reanudada",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{campaign_id}")
async def cancel_campaign(
    campaign_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Cancelar una campaña"""
    try:
        success = queue_manager.cancel_campaign(campaign_id)
        if not success:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
        return {
            "success": True,
            "message": f"Campaña {campaign_id} cancelada",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{campaign_id}/cancel")
async def cancel_campaign_explicit(
    campaign_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Cancelar campaña vía endpoint explícito /cancel."""
    return await cancel_campaign(campaign_id=campaign_id, current_user=current_user)
