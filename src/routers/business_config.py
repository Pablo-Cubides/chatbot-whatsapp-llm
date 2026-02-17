"""
Business Configuration API Router.
Extracted from admin_panel.py — manages business config, export/import.
"""

import io
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from src.services.auth_system import get_current_user, require_admin

logger = logging.getLogger(__name__)

# Business config is imported lazily to avoid circular imports.
# It's a singleton loaded at admin_panel startup.
try:
    from business_config_manager import business_config
except ImportError:
    try:
        from src.services.business_config_manager import business_config
    except ImportError:
        business_config = None  # type: ignore[assignment]

router = APIRouter(prefix="/api/business", tags=["business_config"])


@router.get("/config")
async def get_business_config(current_user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Obtiene la configuración actual del negocio"""
    try:
        return JSONResponse(content=business_config.config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def update_business_config(data: dict[str, Any], current_user: dict[str, Any] = Depends(require_admin)) -> JSONResponse:
    """Actualiza la configuración completa del negocio"""
    try:
        business_config.config = business_config._merge_configs(
            business_config.get_default_config(),
            data,
        )

        if business_config.save_config(business_config.config):
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Configuración actualizada exitosamente",
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Error guardando configuración")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/field")
async def update_business_field(data: dict[str, Any], current_user: dict[str, Any] = Depends(require_admin)) -> JSONResponse:
    """Actualiza un campo específico de la configuración"""
    try:
        field_path = data.get("field")
        value = data.get("value")

        if not field_path:
            raise HTTPException(status_code=400, detail="Campo 'field' requerido")

        if business_config.update_field(field_path, value):
            return JSONResponse(
                content={
                    "success": True,
                    "message": f"Campo {field_path} actualizado",
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Error actualizando campo")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fields")
async def get_editable_fields(current_user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Obtiene la lista de campos editables con sus metadatos"""
    try:
        return JSONResponse(content=business_config.get_editable_fields())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/export")
async def export_business_config(current_user: dict[str, Any] = Depends(get_current_user)) -> StreamingResponse:
    """Exporta la configuración como archivo JSON"""
    try:
        config_json = business_config.export_config()

        return StreamingResponse(
            io.StringIO(config_json),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=business_config.json"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/import")
async def import_business_config(
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(require_admin),
) -> JSONResponse:
    """Importa configuración desde archivo JSON"""
    try:
        if not file.filename or not file.filename.endswith(".json"):
            raise HTTPException(status_code=400, detail="Solo se permiten archivos JSON")

        if file.content_type not in {"application/json", "application/octet-stream", "text/plain"}:
            raise HTTPException(status_code=400, detail="Tipo de archivo inválido")

        content = await file.read()
        if len(content) > 2_000_000:
            raise HTTPException(status_code=413, detail="Archivo demasiado grande")

        try:
            config_json = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="El archivo debe estar codificado en UTF-8") from exc

        try:
            import json

            json.loads(config_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="El archivo no contiene JSON válido") from exc

        if business_config.import_config(config_json):
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Configuración importada exitosamente",
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Error importando configuración")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/reset")
async def reset_business_config(current_user: dict[str, Any] = Depends(require_admin)) -> JSONResponse:
    """Reinicia la configuración a los valores por defecto"""
    try:
        default_config = business_config.get_default_config()
        business_config.config = default_config

        if business_config.save_config(default_config):
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Configuración reiniciada a valores por defecto",
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Error reiniciando configuración")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preview")
async def preview_business_config(current_user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Previsualiza cómo se verá el payload generado"""
    try:
        config = business_config.config
        business_info = config.get("business_info", {})
        client_objectives = config.get("client_objectives", {})
        ai_behavior = config.get("ai_behavior", {})

        preview_prompt = business_config._build_main_prompt(config)

        return JSONResponse(
            content={
                "business_name": business_info.get("name"),
                "description": business_info.get("description"),
                "primary_goal": client_objectives.get("primary_goal"),
                "generated_prompt": preview_prompt,
                "personality": ai_behavior.get("personality_traits", []),
                "services": business_info.get("services", []),
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
