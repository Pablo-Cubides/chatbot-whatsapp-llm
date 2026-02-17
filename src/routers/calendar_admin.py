"""Calendar admin/router extracted from admin_panel."""

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from src.services.auth_system import get_current_user, require_admin
from src.services.business_config_manager import business_config

router = APIRouter(tags=["calendar-admin"])

OAUTH_STATE_TTL_SECONDS = 600
_oauth_state_store: dict[str, datetime] = {}


def _replace_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query[key] = [value]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _issue_oauth_state() -> str:
    now = datetime.now(timezone.utc)
    expired = [state for state, created_at in _oauth_state_store.items() if (now - created_at).total_seconds() > OAUTH_STATE_TTL_SECONDS]
    for state in expired:
        _oauth_state_store.pop(state, None)

    state = secrets.token_urlsafe(24)
    _oauth_state_store[state] = now
    return state


def _consume_oauth_state(state: Optional[str]) -> bool:
    if not state:
        return False

    created_at = _oauth_state_store.pop(state, None)
    if created_at is None:
        return False

    return (datetime.now(timezone.utc) - created_at).total_seconds() <= OAUTH_STATE_TTL_SECONDS


def _get_calendar_manager() -> Any | None:
    """Inicializa/actualiza proveedores de calendario desde business_config."""
    try:
        from src.services.calendar_service import CalendarConfig, CalendarProvider, calendar_manager
        from src.services.google_calendar_provider import GoogleCalendarProvider
        from src.services.outlook_calendar_provider import OutlookCalendarProvider
    except Exception:
        return None

    calendar_cfg = business_config.config.get("integrations", {}).get("calendar_booking", {})
    provider_name = calendar_cfg.get("provider", "google_calendar")
    working_hours = calendar_cfg.get("working_hours", {})

    try:
        provider_enum = CalendarProvider(provider_name)
    except Exception:
        provider_enum = CalendarProvider.GOOGLE_CALENDAR
        provider_name = provider_enum.value

    base_config = CalendarConfig(
        provider=provider_enum,
        calendar_id=calendar_cfg.get(provider_name, {}).get("calendar_id", "primary"),
        default_duration_minutes=calendar_cfg.get("default_duration_minutes", 30),
        buffer_between_appointments=calendar_cfg.get("buffer_between_appointments", 15),
        working_hours=working_hours,
    )

    google_provider = calendar_manager._providers.get("google_calendar")
    if not google_provider:
        google_provider = GoogleCalendarProvider(base_config)
        calendar_manager.register_provider(google_provider)
    else:
        google_provider.config = base_config

    outlook_provider = calendar_manager._providers.get("outlook")
    if not outlook_provider:
        outlook_provider = OutlookCalendarProvider(base_config)
        calendar_manager.register_provider(outlook_provider)
    else:
        outlook_provider.config = base_config

    outlook_cfg = calendar_cfg.get("outlook", {})
    try:
        outlook_provider.configure(
            client_id=outlook_cfg.get("client_id", ""),
            client_secret=outlook_cfg.get("client_secret", ""),
            tenant_id=outlook_cfg.get("tenant_id", "common"),
        )
    except Exception:
        pass

    calendar_manager.set_active_provider(provider_name)
    return calendar_manager


@router.get("/api/calendar/status")
async def get_calendar_status(current_user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Retorna estado actual de integración y proveedor de calendario activo."""
    manager = _get_calendar_manager()
    if not manager:
        return JSONResponse(content={"is_ready": False, "available_providers": [], "active_provider": None})
    return JSONResponse(
        content={
            "is_ready": manager.is_ready(),
            "available_providers": manager.get_available_providers(),
            "active_provider": manager._active_provider,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@router.get("/api/calendar/config")
async def get_calendar_config(current_user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Obtiene la configuración persistida de calendar booking."""
    return JSONResponse(content=business_config.config.get("integrations", {}).get("calendar_booking", {}))


@router.post("/api/calendar/config")
async def save_calendar_config(config: dict[str, Any], current_user: dict[str, Any] = Depends(require_admin)) -> JSONResponse:
    """Guarda configuración de calendario y refresca providers en runtime."""
    try:
        current_config = business_config.config
        if "integrations" not in current_config:
            current_config["integrations"] = {}
        if "calendar_booking" not in current_config["integrations"]:
            current_config["integrations"]["calendar_booking"] = {}

        calendar_config = current_config["integrations"]["calendar_booking"]
        for key, value in config.items():
            if isinstance(value, dict) and key in calendar_config and isinstance(calendar_config[key], dict):
                calendar_config[key].update(value)
            else:
                calendar_config[key] = value

        business_config.save_config(current_config)
        _get_calendar_manager()
        return JSONResponse(content={"success": True, "message": "Configuración guardada"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/calendar/google/credentials")
async def upload_google_credentials(credentials: UploadFile = File(...), current_user: dict[str, Any] = Depends(require_admin)) -> JSONResponse:
    """Sube y valida credenciales OAuth de Google Calendar."""
    try:
        if not credentials.filename or not credentials.filename.lower().endswith(".json"):
            raise HTTPException(status_code=400, detail="El archivo de credenciales debe ser JSON (.json)")

        if credentials.content_type not in {"application/json", "application/octet-stream", "text/plain"}:
            raise HTTPException(status_code=400, detail="Tipo de archivo inválido para credenciales")

        content = await credentials.read()
        if len(content) > 1_000_000:
            raise HTTPException(status_code=413, detail="Archivo de credenciales demasiado grande")

        creds_data = json.loads(content)
        if "installed" not in creds_data and "web" not in creds_data:
            raise HTTPException(status_code=400, detail="Archivo de credenciales inválido")

        section = creds_data.get("installed") or creds_data.get("web") or {}
        required_fields = {"client_id", "client_secret", "redirect_uris"}
        if not isinstance(section, dict) or not required_fields.issubset(set(section.keys())):
            raise HTTPException(status_code=400, detail="Credenciales incompletas: faltan campos requeridos")

        config_dir = Path(__file__).resolve().parents[2] / "config"
        config_dir.mkdir(exist_ok=True)
        creds_path = config_dir / "google_credentials.json"
        with open(creds_path, "w", encoding="utf-8") as f:
            json.dump(creds_data, f, ensure_ascii=False, indent=2)

        manager = _get_calendar_manager()
        if manager and manager._providers.get("google_calendar"):
            manager._providers["google_calendar"].set_credentials_path(str(creds_path))

        return JSONResponse(content={"success": True, "message": "Credenciales guardadas correctamente"})
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="El archivo no es un JSON válido")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/calendar/oauth/google/authorize")
async def google_oauth_authorize(current_user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Genera URL de autorización OAuth para Google Calendar."""
    manager = _get_calendar_manager()
    if not manager:
        raise HTTPException(status_code=500, detail="Calendar manager no disponible")

    provider = manager._providers.get("google_calendar")
    if not provider:
        raise HTTPException(status_code=404, detail="Google Calendar provider no configurado")

    state = _issue_oauth_state()
    auth_url = provider.get_oauth_url(state=state)
    if auth_url:
        auth_url = _replace_query_param(auth_url, "state", state)
    if not auth_url:
        raise HTTPException(status_code=500, detail="No se pudo generar URL OAuth")

    return JSONResponse(content={"authorization_url": auth_url})


@router.get("/api/calendar/oauth/google/callback")
async def google_oauth_callback(code: str, state: Optional[str] = None) -> JSONResponse:
    """Procesa callback OAuth de Google y guarda tokens de acceso."""
    if not _consume_oauth_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    manager = _get_calendar_manager()
    if not manager:
        raise HTTPException(status_code=500, detail="Calendar manager no disponible")

    provider = manager._providers.get("google_calendar")
    if not provider:
        raise HTTPException(status_code=404, detail="Google Calendar provider no configurado")

    redirect_uri = "http://localhost:8003/api/calendar/oauth/google/callback"
    success = await provider.handle_oauth_callback(code, redirect_uri, state=state)
    if not success:
        raise HTTPException(status_code=400, detail="OAuth token exchange failed")
    return JSONResponse(content={"success": True, "message": "Google Calendar conectado exitosamente"})


@router.get("/api/calendar/oauth/outlook/authorize")
async def outlook_oauth_authorize(current_user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Genera URL de autorización OAuth para Outlook."""
    manager = _get_calendar_manager()
    if not manager:
        raise HTTPException(status_code=500, detail="Calendar manager no disponible")

    provider = manager._providers.get("outlook")
    if not provider:
        raise HTTPException(status_code=404, detail="Outlook provider no configurado")

    state = _issue_oauth_state()
    auth_url = provider.get_oauth_url(state=state)
    if auth_url:
        auth_url = _replace_query_param(auth_url, "state", state)
    if not auth_url:
        raise HTTPException(status_code=500, detail="No se pudo generar URL OAuth")

    return JSONResponse(content={"authorization_url": auth_url})


@router.get("/api/calendar/oauth/outlook/callback")
async def outlook_oauth_callback(code: str, state: Optional[str] = None) -> JSONResponse:
    """Procesa callback OAuth de Outlook y guarda tokens de acceso."""
    if not _consume_oauth_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    manager = _get_calendar_manager()
    if not manager:
        raise HTTPException(status_code=500, detail="Calendar manager no disponible")

    provider = manager._providers.get("outlook")
    if not provider:
        raise HTTPException(status_code=404, detail="Outlook provider no configurado")

    redirect_uri = "http://localhost:8003/api/calendar/oauth/outlook/callback"
    success = await provider.handle_oauth_callback(code, redirect_uri, state=state)
    if not success:
        raise HTTPException(status_code=400, detail="OAuth token exchange failed")
    return JSONResponse(content={"success": True, "message": "Outlook Calendar conectado exitosamente"})
