"""
🏢 Endpoints de Configuración de Negocio
Gestión de configuración del chatbot, contextos y prompt del sistema.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import os
import json

from src.services.auth_system import get_current_user, require_admin
from src.services.audit_system import log_config_change

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/business", tags=["Business Configuration"])


class BusinessConfigUpdate(BaseModel):
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    business_description: Optional[str] = None
    tone: Optional[str] = None
    language: Optional[str] = None
    custom_instructions: Optional[str] = None
    working_hours: Optional[Dict[str, Any]] = None
    integrations: Optional[Dict[str, Any]] = None


def _get_business_config_path() -> str:
    """Obtiene la ruta del archivo de configuración de negocio."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    return os.path.join(base_dir, 'data', 'business_config.json')


def _load_business_config() -> Dict[str, Any]:
    """Carga la configuración de negocio desde archivo."""
    path = _get_business_config_path()
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading business config: {e}")
    return {}


def _save_business_config(config: Dict[str, Any]) -> bool:
    """Guarda la configuración de negocio en archivo."""
    path = _get_business_config_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving business config: {e}")
        return False


@router.get("/config")
async def get_business_config(current_user: dict = Depends(get_current_user)):
    """
    Obtiene la configuración actual del negocio.
    
    Retorna todos los parámetros de configuración del chatbot.
    """
    config = _load_business_config()
    return {
        "status": "success",
        "config": config
    }


@router.put("/config")
async def update_business_config(
    updates: BusinessConfigUpdate,
    req: Request,
    current_user: dict = Depends(require_admin)
):
    """
    Actualiza la configuración del negocio.
    
    Solo administradores pueden modificar la configuración.
    """
    current_config = _load_business_config()
    
    # Aplicar actualizaciones
    update_dict = updates.dict(exclude_none=True)
    for key, value in update_dict.items():
        if isinstance(value, dict) and key in current_config:
            # Merge para diccionarios anidados
            current_config[key] = {**current_config.get(key, {}), **value}
        else:
            current_config[key] = value
    
    if not _save_business_config(current_config):
        raise HTTPException(
            status_code=500,
            detail="Error guardando configuración"
        )
    
    # Registrar en auditoría
    username = current_user.get("username", "unknown")
    client_ip = req.client.host if req.client else "unknown"
    await log_config_change(username, "business_config", update_dict, client_ip)
    
    return {
        "status": "success",
        "message": "Configuración actualizada",
        "config": current_config
    }


@router.get("/preview-prompt")
async def preview_business_prompt(current_user: dict = Depends(get_current_user)):
    """
    Genera una vista previa del prompt del sistema basado en la configuración actual.
    
    Útil para verificar cómo se verá el contexto del chatbot.
    """
    config = _load_business_config()
    
    # Construir prompt preview
    prompt_parts = []
    
    if config.get("business_name"):
        prompt_parts.append(f"Nombre del negocio: {config['business_name']}")
    
    if config.get("business_type"):
        prompt_parts.append(f"Tipo: {config['business_type']}")
    
    if config.get("business_description"):
        prompt_parts.append(f"Descripción: {config['business_description']}")
    
    if config.get("tone"):
        prompt_parts.append(f"Tono: {config['tone']}")
    
    if config.get("custom_instructions"):
        prompt_parts.append(f"Instrucciones especiales: {config['custom_instructions']}")
    
    preview = "\n".join(prompt_parts) if prompt_parts else "Sin configuración definida"
    
    return {
        "status": "success",
        "preview": preview,
        "config_summary": {
            "has_name": bool(config.get("business_name")),
            "has_type": bool(config.get("business_type")),
            "has_description": bool(config.get("business_description")),
            "has_tone": bool(config.get("tone")),
            "has_custom_instructions": bool(config.get("custom_instructions")),
            "has_working_hours": bool(config.get("working_hours")),
            "has_integrations": bool(config.get("integrations"))
        }
    }


@router.post("/reset")
async def reset_business_config(
    req: Request,
    current_user: dict = Depends(require_admin)
):
    """
    Resetea la configuración del negocio a valores por defecto.
    
    ⚠️ Esta acción no se puede deshacer.
    """
    default_config = {
        "business_name": "Mi Negocio",
        "business_type": "general",
        "business_description": "",
        "tone": "profesional",
        "language": "es",
        "custom_instructions": "",
        "working_hours": {
            "monday": {"start": "09:00", "end": "18:00"},
            "tuesday": {"start": "09:00", "end": "18:00"},
            "wednesday": {"start": "09:00", "end": "18:00"},
            "thursday": {"start": "09:00", "end": "18:00"},
            "friday": {"start": "09:00", "end": "18:00"},
            "saturday": {"start": "09:00", "end": "14:00"},
            "sunday": None
        },
        "integrations": {}
    }
    
    if not _save_business_config(default_config):
        raise HTTPException(
            status_code=500,
            detail="Error reseteando configuración"
        )
    
    # Registrar en auditoría
    username = current_user.get("username", "unknown")
    client_ip = req.client.host if req.client else "unknown"
    await log_config_change(username, "business_config_reset", {}, client_ip)
    
    return {
        "status": "success",
        "message": "Configuración reseteada a valores por defecto",
        "config": default_config
    }
