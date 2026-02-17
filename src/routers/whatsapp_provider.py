"""WhatsApp provider configuration routes extracted from admin_panel.py."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.services.audit_system import log_config_change
from src.services.auth_system import get_current_user, require_admin
from src.services.business_config_manager import business_config

router = APIRouter(tags=["whatsapp", "provider"])


class WhatsAppProviderConfig(BaseModel):
    mode: str  # web, cloud, both
    cloud_api: Optional[dict[str, str]] = None


@router.get("/api/whatsapp/provider/config")
async def get_whatsapp_provider_config(current_user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Obtiene la configuración actual del proveedor WhatsApp."""
    try:
        config = business_config.config.get("whatsapp_provider", {"mode": "web", "cloud_api": {}})

        if config.get("cloud_api", {}).get("access_token"):
            token = config["cloud_api"].get("access_token", "")
            masked_token = token[:10] + "..." if len(token) > 10 else ""
            config = {**config, "cloud_api": {**config.get("cloud_api", {}), "access_token_masked": masked_token}}

        return JSONResponse(content=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/whatsapp/provider/config")
async def update_whatsapp_provider_config(
    config: WhatsAppProviderConfig, current_user: dict[str, Any] = Depends(require_admin)
) -> JSONResponse:
    """Actualiza la configuración del proveedor WhatsApp."""
    try:
        if config.mode not in {"web", "cloud", "both"}:
            raise HTTPException(status_code=400, detail="Mode debe ser 'web', 'cloud', o 'both'")

        whatsapp_config = {"mode": config.mode, "cloud_api": config.cloud_api or {}}
        business_config.config["whatsapp_provider"] = whatsapp_config

        if business_config.save_config(business_config.config):
            log_config_change(
                current_user.get("username", "admin"),
                current_user.get("role", "admin"),
                "whatsapp_provider",
                {"mode": config.mode},
            )
            return JSONResponse(content={"success": True, "message": f"Proveedor WhatsApp configurado en modo: {config.mode}"})

        raise HTTPException(status_code=500, detail="Error guardando configuración")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/whatsapp/cloud/credentials")
async def update_cloud_api_credentials(data: dict[str, str], current_user: dict[str, Any] = Depends(require_admin)) -> JSONResponse:
    """Actualiza las credenciales del Cloud API de WhatsApp."""
    try:
        required_fields = ["access_token", "phone_number_id"]
        for field in required_fields:
            if not data.get(field):
                raise HTTPException(status_code=400, detail=f"Campo '{field}' es requerido")

        cloud_config = {
            "access_token": data.get("access_token", ""),
            "phone_number_id": data.get("phone_number_id", ""),
            "verify_token": data.get("verify_token", ""),
            "business_account_id": data.get("business_account_id", ""),
        }

        if "whatsapp_provider" not in business_config.config:
            business_config.config["whatsapp_provider"] = {"mode": "cloud"}

        business_config.config["whatsapp_provider"]["cloud_api"] = cloud_config

        if business_config.save_config(business_config.config):
            log_config_change(
                current_user.get("username", "admin"),
                current_user.get("role", "admin"),
                "whatsapp_cloud_credentials",
                {"phone_number_id": data.get("phone_number_id")},
            )
            return JSONResponse(content={"success": True, "message": "Credenciales de Cloud API actualizadas"})

        raise HTTPException(status_code=500, detail="Error guardando credenciales")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
