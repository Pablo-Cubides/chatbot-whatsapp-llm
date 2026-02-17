"""Analysis settings and adaptive layer routes extracted from admin_panel.py."""

import logging
from typing import Any, Optional

import chat_sessions
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.services.adaptive_layer import adaptive_layer_manager
from src.services.audit_system import log_config_change
from src.services.auth_system import get_current_user, require_admin
from src.services.business_config_manager import business_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis", "adaptive"])


class AnalysisSettings(BaseModel):
    deep_analysis_enabled: Optional[bool] = True
    deep_analysis_trigger_conversations: Optional[int] = 50
    deep_analysis_trigger_days: Optional[int] = 7
    image_analysis_enabled: Optional[bool] = True
    audio_transcription_enabled: Optional[bool] = True
    whisper_model_size: Optional[str] = "base"
    whisper_device: Optional[str] = "cpu"


@router.get("/api/settings/analysis")
async def get_analysis_settings(current_user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Obtiene la configuración de análisis."""
    try:
        settings = business_config.config.get(
            "analysis_settings",
            {
                "deep_analysis_enabled": True,
                "deep_analysis_trigger_conversations": 50,
                "deep_analysis_trigger_days": 7,
                "image_analysis_enabled": True,
                "audio_transcription_enabled": True,
                "whisper_model_size": "base",
                "whisper_device": "cpu",
            },
        )
        return JSONResponse(content=settings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/settings/analysis")
async def update_analysis_settings(settings: AnalysisSettings, current_user: dict[str, Any] = Depends(require_admin)) -> JSONResponse:
    """Actualiza la configuración de análisis."""
    try:
        analysis_config = {
            "deep_analysis_enabled": settings.deep_analysis_enabled,
            "deep_analysis_trigger_conversations": settings.deep_analysis_trigger_conversations,
            "deep_analysis_trigger_days": settings.deep_analysis_trigger_days,
            "image_analysis_enabled": settings.image_analysis_enabled,
            "audio_transcription_enabled": settings.audio_transcription_enabled,
            "whisper_model_size": settings.whisper_model_size,
            "whisper_device": settings.whisper_device,
        }

        business_config.config["analysis_settings"] = analysis_config

        if business_config.save_config(business_config.config):
            adaptive_layer_manager.business_config = business_config
            adaptive_layer_manager.sync_runtime_settings()
            log_config_change(
                current_user.get("username", "admin"),
                current_user.get("role", "admin"),
                "analysis_settings",
                analysis_config,
            )
            return JSONResponse(content={"success": True, "message": "Configuración de análisis actualizada"})

        raise HTTPException(status_code=500, detail="Error guardando configuración")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/adaptive/status")
async def get_adaptive_status(current_user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Estado runtime de la capa adaptativa."""
    adaptive_layer_manager.business_config = business_config
    adaptive_layer_manager.sync_runtime_settings()
    return JSONResponse(content=adaptive_layer_manager.get_status())


@router.post("/api/adaptive/run-now")
async def run_adaptive_now(payload: dict[str, int] | None = None, current_user: dict[str, Any] = Depends(require_admin)) -> JSONResponse:
    """Fuerza un ciclo de análisis adaptativo (admin)."""
    adaptive_layer_manager.business_config = business_config
    adaptive_layer_manager.sync_runtime_settings()

    requested_limit = (payload or {}).get("limit", 25)
    conversations = chat_sessions.load_recent_conversations(limit=max(1, min(int(requested_limit), 100)))
    result = await adaptive_layer_manager.run_analysis(conversations=conversations, force=True)

    try:
        import os

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        overrides = adaptive_layer_manager.get_runtime_overrides()
        adaptive_layer_manager.apply_runtime_overrides(overrides, project_root)
    except Exception as adaptive_error:
        logger.warning(f"Adaptive apply warning: {adaptive_error}")

    return JSONResponse(content=result)
