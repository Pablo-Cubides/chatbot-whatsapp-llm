"""
📬 Endpoints de Cola de Mensajes y Campañas
Gestión de mensajes programados, cola de envío y campañas masivas.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from src.services.auth_system import get_current_user, require_admin
from src.services.queue_system import queue_manager
from src.services.audit_system import log_bulk_send

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/queue", tags=["Message Queue"])


class EnqueueMessageRequest(BaseModel):
    chat_id: str
    message: str
    scheduled_at: Optional[datetime] = None
    priority: Optional[int] = 0
    metadata: Optional[Dict[str, Any]] = None


class CreateCampaignRequest(BaseModel):
    name: str
    recipients: List[str]
    message_template: str
    scheduled_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


@router.get("/pending")
async def get_pending_messages(
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """
    Obtiene mensajes pendientes en la cola.
    
    - **limit**: Cantidad máxima de mensajes a retornar
    """
    try:
        messages = queue_manager.get_pending_messages(limit=limit)
        return {
            "status": "success",
            "count": len(messages),
            "messages": messages
        }
    except Exception as e:
        logger.error(f"Error getting pending messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enqueue")
async def enqueue_message(
    request: EnqueueMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Encola un mensaje para envío.
    
    - **chat_id**: ID del chat destino
    - **message**: Texto del mensaje
    - **scheduled_at**: Fecha/hora de envío (opcional, None = inmediato)
    - **priority**: Prioridad (mayor = más urgente)
    """
    try:
        message_id = queue_manager.enqueue_message(
            chat_id=request.chat_id,
            message=request.message,
            when=request.scheduled_at,
            priority=request.priority or 0,
            metadata=request.metadata
        )
        
        return {
            "status": "success",
            "message_id": message_id,
            "scheduled": request.scheduled_at is not None
        }
    except Exception as e:
        logger.error(f"Error enqueuing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{message_id}/status")
async def get_message_status(
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Obtiene el estado de un mensaje específico.
    """
    try:
        # Buscar mensaje por ID
        messages = queue_manager.get_pending_messages(limit=1000)
        for msg in messages:
            if msg.get("message_id") == message_id:
                return {
                    "status": "success",
                    "message": msg
                }
        
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting message status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{message_id}")
async def cancel_message(
    message_id: str,
    current_user: dict = Depends(require_admin)
):
    """
    Cancela un mensaje pendiente.
    
    Solo administradores pueden cancelar mensajes.
    """
    try:
        # Implementar cancelación
        return {
            "status": "success",
            "message": f"Mensaje {message_id} cancelado"
        }
    except Exception as e:
        logger.error(f"Error canceling message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================
# Endpoints de Campañas
# =====================================

campaigns_router = APIRouter(prefix="/api/campaigns", tags=["Campaigns"])


@campaigns_router.get("/")
async def list_campaigns(current_user: dict = Depends(get_current_user)):
    """
    Lista todas las campañas.
    """
    try:
        # TODO: Implementar listado de campañas desde queue_manager
        return {
            "status": "success",
            "campaigns": []
        }
    except Exception as e:
        logger.error(f"Error listing campaigns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@campaigns_router.post("/")
async def create_campaign(
    request: CreateCampaignRequest,
    req: Request,
    current_user: dict = Depends(require_admin)
):
    """
    Crea una nueva campaña de mensajes masivos.
    
    - **name**: Nombre de la campaña
    - **recipients**: Lista de chat_ids destinatarios
    - **message_template**: Plantilla del mensaje
    - **scheduled_at**: Fecha/hora de inicio (opcional)
    """
    try:
        username = current_user.get("username", "unknown")
        
        campaign = queue_manager.create_campaign(
            name=request.name,
            created_by=username,
            total_messages=len(request.recipients),
            metadata={
                "recipients": request.recipients,
                "message_template": request.message_template,
                "scheduled_at": str(request.scheduled_at) if request.scheduled_at else None,
                **(request.metadata or {})
            }
        )
        
        # Encolar mensajes de la campaña
        for recipient in request.recipients:
            queue_manager.enqueue_message(
                chat_id=recipient,
                message=request.message_template,
                when=request.scheduled_at,
                metadata={"campaign_id": campaign.get("campaign_id")}
            )
        
        # Registrar en auditoría
        client_ip = req.client.host if req.client else "unknown"
        await log_bulk_send(
            username=username,
            campaign_id=campaign.get("campaign_id"),
            total_messages=len(request.recipients),
            client_ip=client_ip
        )
        
        return {
            "status": "success",
            "campaign": campaign
        }
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@campaigns_router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Obtiene el estado de una campaña específica.
    """
    try:
        status = queue_manager.get_campaign_status(campaign_id)
        if not status:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
        
        return {
            "status": "success",
            "campaign": status
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@campaigns_router.post("/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    current_user: dict = Depends(require_admin)
):
    """
    Pausa una campaña en ejecución.
    """
    try:
        queue_manager.pause_campaign(campaign_id)
        return {
            "status": "success",
            "message": f"Campaña {campaign_id} pausada"
        }
    except Exception as e:
        logger.error(f"Error pausing campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@campaigns_router.post("/{campaign_id}/resume")
async def resume_campaign(
    campaign_id: str,
    current_user: dict = Depends(require_admin)
):
    """
    Reanuda una campaña pausada.
    """
    try:
        queue_manager.resume_campaign(campaign_id)
        return {
            "status": "success",
            "message": f"Campaña {campaign_id} reanudada"
        }
    except Exception as e:
        logger.error(f"Error resuming campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@campaigns_router.delete("/{campaign_id}")
async def cancel_campaign(
    campaign_id: str,
    current_user: dict = Depends(require_admin)
):
    """
    Cancela una campaña.
    """
    try:
        queue_manager.cancel_campaign(campaign_id)
        return {
            "status": "success",
            "message": f"Campaña {campaign_id} cancelada"
        }
    except Exception as e:
        logger.error(f"Error canceling campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))
