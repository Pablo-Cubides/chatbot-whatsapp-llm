"""Online/local model management routes extracted from admin_panel.py."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from crypto import encrypt_text
from src.models.admin_db import get_session
from src.models.models import ModelConfig
from src.routers.deps import verify_token
from src.services.auth_system import get_current_user

router = APIRouter(tags=["models-online"])


@router.get("/api/models/local")
def api_list_local_models(current_user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Lista modelos locales configurados en base de datos."""
    session = get_session()
    try:
        models = session.query(ModelConfig).filter(ModelConfig.model_type == "local").all()
        return [
            {"id": m.id, "name": m.name, "provider": m.provider, "model_type": m.model_type, "active": m.active}
            for m in models
        ]
    finally:
        session.close()


@router.get("/api/models/online")
def api_list_online_models(current_user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Lista modelos online configurados con su metadata no sensible."""
    session = get_session()
    try:
        models = session.query(ModelConfig).filter(ModelConfig.model_type == "online").all()
        return [
            {
                "id": m.id,
                "name": m.name,
                "provider": m.provider,
                "model_type": m.model_type,
                "active": m.active,
                "config": m.config,
            }
            for m in models
        ]
    finally:
        session.close()


@router.get("/api/models/online/available")
def api_available_online_models(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Retorna catálogo estático de proveedores/modelos online soportados."""
    return {
        "google": {
            "provider": "google",
            "models": [
                {"id": "gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash Lite", "description": "Recomendado: rápido, gratis"},
                {
                    "id": "gemini-2.5-flash",
                    "name": "Gemini 2.5 Flash",
                    "description": "Mejor calidad, tier gratuito disponible",
                },
                {
                    "id": "gemini-3.1-flash-lite-preview",
                    "name": "Gemini 3.1 Flash Lite (preview)",
                    "description": "Más nuevo, gratis (preview)",
                },
            ],
        },
        "openai": {
            "provider": "openai",
            "models": [
                {"id": "gpt-5.4", "name": "GPT-5.4", "description": "Máxima calidad de OpenAI"},
                {"id": "gpt-5.4-mini", "name": "GPT-5.4 Mini", "description": "Equilibrio calidad/precio (recomendado)"},
                {"id": "gpt-5.4-nano", "name": "GPT-5.4 Nano", "description": "El más barato de OpenAI"},
            ],
        },
        "anthropic": {
            "provider": "anthropic",
            "models": [
                {"id": "claude-opus-4-7", "name": "Claude Opus 4.7", "description": "Máxima capacidad"},
                {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "description": "Mejor calidad/precio"},
                {
                    "id": "claude-haiku-4-5-20251001",
                    "name": "Claude Haiku 4.5",
                    "description": "Rápido y barato (recomendado)",
                },
            ],
        },
        "x-ai": {
            "provider": "x-ai",
            "models": [
                {
                    "id": "grok-4-1-fast",
                    "name": "Grok 4.1 Fast",
                    "description": "Rápido y económico, 2M contexto (recomendado)",
                },
                {"id": "grok-4", "name": "Grok 4", "description": "Flagship completo, más caro"},
            ],
        },
    }


class OnlineModelConfig(BaseModel):
    name: str
    provider: str
    model_id: str
    api_key: str
    base_url: str | None = None
    active: bool = True


@router.post("/api/models/online")
def api_create_online_model(
    config: OnlineModelConfig, current_user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    """Crea un modelo online y almacena API key encriptada."""
    session = get_session()
    try:
        encrypted_key = encrypt_text(config.api_key)

        model_config = {"model_id": config.model_id, "api_key_encrypted": encrypted_key, "base_url": config.base_url}

        model = ModelConfig(
            name=config.name, provider=config.provider, model_type="online", config=model_config, active=config.active
        )

        session.add(model)
        session.commit()
        session.refresh(model)

        return {
            "id": model.id,
            "name": model.name,
            "provider": model.provider,
            "model_type": model.model_type,
            "active": model.active,
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.put("/api/models/online/{model_id}")
def api_update_online_model(
    model_id: int, config: OnlineModelConfig, current_user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    """Actualiza un modelo online existente por ID."""
    session = get_session()
    try:
        model = session.query(ModelConfig).filter(ModelConfig.id == model_id, ModelConfig.model_type == "online").first()
        if not model:
            raise HTTPException(status_code=404, detail="Online model not found")

        encrypted_key = encrypt_text(config.api_key)

        model_config = {"model_id": config.model_id, "api_key_encrypted": encrypted_key, "base_url": config.base_url}

        model.name = config.name
        model.provider = config.provider
        model.config = model_config
        model.active = config.active

        session.commit()

        return {
            "id": model.id,
            "name": model.name,
            "provider": model.provider,
            "model_type": model.model_type,
            "active": model.active,
        }
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/api/models/online/{model_id}")
def api_delete_online_model(model_id: int, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Elimina un modelo online por ID."""
    session = get_session()
    try:
        model = session.query(ModelConfig).filter(ModelConfig.id == model_id, ModelConfig.model_type == "online").first()
        if not model:
            raise HTTPException(status_code=404, detail="Online model not found")

        session.delete(model)
        session.commit()

        return {"success": True, "message": "Online model deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/api/admin/migrate-model-types")
def api_migrate_model_types(user: str = Depends(verify_token)) -> dict[str, Any]:
    """Migrate existing models to have proper model_type field."""
    _ = user
    session = get_session()
    try:
        result = session.execute(text("UPDATE models SET model_type = 'local' WHERE model_type IS NULL OR model_type = ''"))
        models_updated = getattr(result, "rowcount", 0)
        session.commit()

        return {
            "success": True,
            "models_updated": models_updated,
            "message": f"Updated {models_updated} models to have model_type='local'",
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
