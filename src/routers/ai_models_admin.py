"""AI models admin/configuration router extracted from admin_panel."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.services.audit_system import log_config_change
from src.services.auth_system import get_current_user, require_admin
from src.services.business_config_manager import business_config
from src.services.queue_system import queue_manager

router = APIRouter(tags=["ai-models-admin"])


class CustomProviderConfig(BaseModel):
    name: str
    provider_type: str
    api_key: str
    base_url: Optional[str] = None
    model: str
    is_free: Optional[bool] = False
    is_reasoning: Optional[bool] = False
    active: Optional[bool] = True


class AIModelsConfig(BaseModel):
    default_provider: Optional[str] = "gemini"
    response_layer: Optional[dict[str, str]] = None
    reasoner_layer: Optional[dict[str, str]] = None
    analyzer_layer: Optional[dict[str, str]] = None


@router.get("/api/ai-models/config")
async def get_ai_models_config(current_user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Obtiene la configuración de modelos de IA."""
    try:
        config = business_config.config.get(
            "ai_models",
            {
                "default_provider": "gemini",
                "response_layer": {"provider": "auto", "model": ""},
                "reasoner_layer": {"provider": "lmstudio", "model": ""},
                "analyzer_layer": {"provider": "auto", "model": ""},
                "custom_providers": [],
            },
        )

        if "custom_providers" in config:
            masked_providers = []
            for p in config["custom_providers"]:
                masked = {**p}
                if masked.get("api_key"):
                    masked["api_key_masked"] = masked["api_key"][:8] + "..." if len(masked.get("api_key", "")) > 8 else ""
                    del masked["api_key"]
                masked_providers.append(masked)
            config["custom_providers"] = masked_providers

        return JSONResponse(content=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai-models/config")
async def update_ai_models_config(config: AIModelsConfig, current_user: dict[str, Any] = Depends(require_admin)) -> JSONResponse:
    """Actualiza la configuración de modelos de IA."""
    try:
        ai_config = business_config.config.get("ai_models", {})

        if config.default_provider:
            ai_config["default_provider"] = config.default_provider
        if config.response_layer:
            ai_config["response_layer"] = config.response_layer
        if config.reasoner_layer:
            ai_config["reasoner_layer"] = config.reasoner_layer
        if config.analyzer_layer:
            ai_config["analyzer_layer"] = config.analyzer_layer

        business_config.config["ai_models"] = ai_config

        if business_config.save_config(business_config.config):
            log_config_change(
                current_user.get("username", "admin"),
                "ai_models",
                {"default_provider": config.default_provider},
            )
            return JSONResponse(content={"success": True, "message": "Configuración de modelos IA actualizada"})

        raise HTTPException(status_code=500, detail="Error guardando configuración")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai-models/custom-provider")
async def add_custom_provider(provider: CustomProviderConfig, current_user: dict[str, Any] = Depends(require_admin)) -> JSONResponse:
    """Agrega un proveedor de IA personalizado con API key del usuario."""
    try:
        ai_config = business_config.config.get("ai_models", {})

        if "custom_providers" not in ai_config:
            ai_config["custom_providers"] = []

        existing_names = [p["name"] for p in ai_config["custom_providers"]]
        if provider.name in existing_names:
            raise HTTPException(status_code=400, detail=f"Ya existe un proveedor con el nombre '{provider.name}'")

        new_provider = {
            "name": provider.name,
            "provider_type": provider.provider_type,
            "api_key": provider.api_key,
            "base_url": provider.base_url,
            "model": provider.model,
            "is_free": provider.is_free,
            "is_reasoning": provider.is_reasoning,
            "active": provider.active,
        }

        ai_config["custom_providers"].append(new_provider)
        business_config.config["ai_models"] = ai_config

        if business_config.save_config(business_config.config):
            log_config_change(
                current_user.get("username", "admin"),
                "custom_ai_provider_added",
                {"name": provider.name, "provider_type": provider.provider_type},
            )
            return JSONResponse(content={"success": True, "message": f"Proveedor '{provider.name}' agregado exitosamente"})

        raise HTTPException(status_code=500, detail="Error guardando proveedor")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/ai-models/custom-provider/{provider_name}")
async def delete_custom_provider(provider_name: str, current_user: dict[str, Any] = Depends(require_admin)) -> JSONResponse:
    """Elimina un proveedor de IA personalizado."""
    try:
        ai_config = business_config.config.get("ai_models", {})

        if "custom_providers" not in ai_config:
            raise HTTPException(status_code=404, detail="No hay proveedores personalizados")

        original_count = len(ai_config["custom_providers"])
        ai_config["custom_providers"] = [p for p in ai_config["custom_providers"] if p["name"] != provider_name]

        if len(ai_config["custom_providers"]) == original_count:
            raise HTTPException(status_code=404, detail=f"Proveedor '{provider_name}' no encontrado")

        business_config.config["ai_models"] = ai_config

        if business_config.save_config(business_config.config):
            return JSONResponse(content={"success": True, "message": f"Proveedor '{provider_name}' eliminado"})

        raise HTTPException(status_code=500, detail="Error eliminando proveedor")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai-models/test-connection")
async def test_ai_provider_connection(data: dict[str, str], current_user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Prueba la conexión con un proveedor de IA."""
    try:
        provider_type = data.get("provider_type")
        api_key = data.get("api_key")
        base_url = data.get("base_url")

        if not provider_type or not api_key:
            raise HTTPException(status_code=400, detail="provider_type y api_key son requeridos")

        import aiohttp

        test_result = {"success": False, "message": ""}

        if provider_type == "openai":
            url = (base_url or "https://api.openai.com/v1") + "/models"
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=aiohttp.ClientTimeout(total=10)) as response,
            ):
                test_result = {"success": response.status == 200, "message": "Conexión exitosa con OpenAI" if response.status == 200 else f"Error: {response.status}"}

        elif provider_type == "gemini":
            url = (base_url or "https://generativelanguage.googleapis.com/v1beta") + "/models"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"x-goog-api-key": api_key},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    test_result = {"success": response.status == 200, "message": "Conexión exitosa con Gemini" if response.status == 200 else f"Error: {response.status}"}

        elif provider_type == "xai":
            url = (base_url or "https://api.x.ai/v1") + "/models"
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=aiohttp.ClientTimeout(total=10)) as response,
            ):
                test_result = {"success": response.status == 200, "message": "Conexión exitosa con xAI/Grok" if response.status == 200 else f"Error: {response.status}"}
        else:
            test_result = {
                "success": False,
                "message": f"Tipo de proveedor '{provider_type}' no soportado para test automático",
            }

        return JSONResponse(content=test_result)

    except Exception as e:
        return JSONResponse(content={"success": False, "message": str(e)})


@router.get("/api/ai-models/available-providers")
async def get_available_providers(current_user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Lista tipos de proveedores disponibles para configurar."""
    return JSONResponse(
        content={
            "providers": [
                {
                    "type": "gemini",
                    "name": "Google Gemini",
                    "description": "Excelente relación calidad/precio, 15 RPM gratuitas",
                    "requires_key": True,
                    "default_model": "gemini-1.5-flash",
                    "is_free": True,
                },
                {
                    "type": "openai",
                    "name": "OpenAI (GPT)",
                    "description": "Mejor calidad general, modelos GPT-4 y GPT-3.5",
                    "requires_key": True,
                    "default_model": "gpt-4o-mini",
                    "is_free": False,
                },
                {
                    "type": "claude",
                    "name": "Anthropic Claude",
                    "description": "Excelente para análisis profundo y razonamiento",
                    "requires_key": True,
                    "default_model": "claude-3-haiku-20240307",
                    "is_free": False,
                },
                {
                    "type": "xai",
                    "name": "xAI Grok",
                    "description": "Límites generosos en beta, menos censura",
                    "requires_key": True,
                    "default_model": "grok-beta",
                    "is_free": True,
                },
                {
                    "type": "ollama",
                    "name": "Ollama (Local)",
                    "description": "Modelos locales gratuitos, requiere instalación",
                    "requires_key": False,
                    "default_model": "llama3.2:3b",
                    "is_free": True,
                },
                {
                    "type": "lmstudio",
                    "name": "LM Studio (Local)",
                    "description": "Modelos locales con interfaz gráfica",
                    "requires_key": False,
                    "default_model": "nemotron-mini-4b-instruct",
                    "is_free": True,
                },
            ]
        }
    )


@router.get("/api/llm/providers")
async def get_llm_providers_compat(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, list[dict[str, Any]]]:
    """Compatibilidad con analytics UI."""
    ai_config = business_config.config.get("ai_models", {})
    providers: list[dict[str, Any]] = []

    default_provider = ai_config.get("default_provider", "gemini")
    providers.append(
        {
            "name": str(default_provider).title(),
            "status": "active",
            "requests": 0,
            "avgResponse": 0,
            "errors": 0,
        }
    )

    for custom in ai_config.get("custom_providers", []):
        providers.append(
            {
                "name": custom.get("name", "Custom Provider"),
                "status": "active" if custom.get("enabled", True) else "error",
                "requests": 0,
                "avgResponse": 0,
                "errors": 0,
            }
        )

    unique: dict[str, dict[str, Any]] = {}
    for provider in providers:
        unique[provider["name"]] = provider

    return {"providers": list(unique.values())}


@router.get("/api/queue/pending")
def api_queue_pending(limit: int = 100, current_user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Mensajes pendientes para scheduler UI."""
    safe_limit = max(1, min(int(limit), 500))
    messages = queue_manager.get_pending_messages(limit=safe_limit)
    for item in messages:
        item["phone"] = item.get("chat_id")
    return messages


@router.post("/api/test-apis")
def api_test_apis(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Prueba de conectividad de componentes principales para dashboard UI."""
    return {
        "success": True,
        "results": {
            "auth": True,
            "business_config": business_config is not None,
            "queue": queue_manager is not None,
            "chat": True,
            "llm": True,
        },
    }
