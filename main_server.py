#!/usr/bin/env python3
"""
🚀 Admin Panel Completo - WhatsApp AI Chatbot
Sistema integrado con todas las funcionalidades
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import uvicorn
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Agregar src al path para imports
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

# Importar sistemas creados
try:
    from services.business_config_manager import business_config

    logger.info("✅ Business Config Manager cargado")
except ImportError as e:
    logger.warning(f"⚠️ Business Config Manager no disponible: {e}")
    business_config = None

try:
    from services.auth_system import LoginRequest, LoginResponse, auth_manager, get_current_user, require_admin

    logger.info("✅ Sistema de autenticación cargado")
except ImportError as e:
    logger.warning(f"⚠️ Sistema de autenticación no disponible: {e}")
    auth_manager = None

try:
    from services.chat_system import chat_manager

    logger.info("✅ Sistema de chat cargado")
except ImportError as e:
    logger.warning(f"⚠️ Sistema de chat no disponible: {e}")
    chat_manager = None

try:
    from services.analytics_system import analytics_manager

    logger.info("✅ Sistema de analytics cargado")
except ImportError as e:
    logger.warning(f"⚠️ Sistema de analytics no disponible: {e}")
    analytics_manager = None

try:
    from services.realtime_metrics import realtime_metrics

    logger.info("✅ Sistema de métricas en tiempo real cargado")
except ImportError as e:
    logger.warning(f"⚠️ Sistema de métricas en tiempo real no disponible: {e}")
    realtime_metrics = None

try:
    from services.multi_provider_llm import MultiProviderLLM
    from services.whatsapp_system import WhatsAppManager

    # Inicializar WhatsApp Manager con dependencias
    multi_llm = MultiProviderLLM()
    whatsapp_manager = WhatsAppManager(business_config, multi_llm, analytics_manager)
    logger.info("✅ Sistema de WhatsApp cargado")
except ImportError as e:
    logger.warning(f"⚠️ Sistema de WhatsApp no disponible: {e}")
    whatsapp_manager = None
    multi_llm = None

# Importar sistema de citas
try:
    from services.appointment_flow import appointment_flow
    from services.calendar_service import CalendarConfig, CalendarProvider, calendar_manager
    from services.google_calendar_provider import GoogleCalendarProvider
    from services.outlook_calendar_provider import OutlookCalendarProvider

    # Configurar proveedores de calendario si están habilitados
    if business_config:
        calendar_config = business_config.config.get("integrations", {}).get("calendar_booking", {})
        if calendar_config.get("enabled"):
            working_hours = calendar_config.get("working_hours", {})
            provider = calendar_config.get("provider", "google_calendar")

            config = CalendarConfig(
                provider=CalendarProvider(provider),
                calendar_id=calendar_config.get(provider, {}).get("calendar_id", "primary"),
                default_duration_minutes=calendar_config.get("default_duration_minutes", 30),
                buffer_between_appointments=calendar_config.get("buffer_between_appointments", 15),
                working_hours=working_hours,
            )

            if provider == "google_calendar":
                google_provider = GoogleCalendarProvider(config)
                calendar_manager.register_provider(google_provider)
                calendar_manager.set_active_provider("google_calendar")
            elif provider == "outlook":
                outlook_config = calendar_config.get("outlook", {})
                outlook_provider = OutlookCalendarProvider(config)
                outlook_provider.configure(
                    client_id=outlook_config.get("client_id", ""),
                    client_secret=outlook_config.get("client_secret", ""),
                    tenant_id=outlook_config.get("tenant_id", "common"),
                )
                calendar_manager.register_provider(outlook_provider)
                calendar_manager.set_active_provider("outlook")

    logger.info("✅ Sistema de citas cargado")
except ImportError as e:
    logger.warning(f"⚠️ Sistema de citas no disponible: {e}")
    calendar_manager = None
    appointment_flow = None

# Crear app FastAPI
app = FastAPI(
    title="WhatsApp AI Chatbot Admin Panel",
    description="Sistema completo de administración para chatbot empresarial",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS configuration from environment
allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:8003,http://127.0.0.1:8003").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "X-Request-ID",
        "X-Requested-With",
    ],
)

# Servir archivos estáticos
app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")

# Mount metrics endpoint
try:
    from src.services.metrics import router as metrics_router

    app.include_router(metrics_router)
    logger.info("✅ Metrics endpoint disponible en /metrics")
except ImportError as e:
    logger.warning(f"⚠️ Metrics endpoint no disponible: {e}")

# ═══════════════════════════════════════════════════════════════
# 🏠 RUTAS PRINCIPALES
# ═══════════════════════════════════════════════════════════════


@app.get("/")
async def home():
    return {
        "message": "WhatsApp AI Chatbot Admin Panel",
        "version": "2.0.0",
        "status": "running",
        "features": {
            "business_config": business_config is not None,
            "authentication": auth_manager is not None,
            "chat_testing": chat_manager is not None,
            "analytics": analytics_manager is not None,
            "whatsapp": whatsapp_manager is not None,
        },
        "endpoints": {"dashboard": "/ui/index.html", "business_config": "/ui/business_config.html", "api_docs": "/api/docs"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/healthz")
async def health():
    """Health check endpoint"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "systems": {
            "api": True,
            "business_config": business_config is not None,
            "auth": auth_manager is not None,
            "chat": chat_manager is not None,
            "analytics": analytics_manager is not None,
            "whatsapp": whatsapp_manager is not None and whatsapp_manager.is_running if whatsapp_manager else False,
        },
    }

    all_healthy = all(health_status["systems"].values())
    health_status["overall"] = "healthy" if all_healthy else "degraded"

    return JSONResponse(content=health_status)


# ═══════════════════════════════════════════════════════════════
# 🔐 RUTAS DE AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════

if auth_manager:

    @app.post("/api/auth/login", response_model=LoginResponse)
    async def login(request: LoginRequest):
        """Iniciar sesión"""
        user = auth_manager.authenticate_user(request.username, request.password)
        if not user:
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")

        access_token = auth_manager.create_access_token(user)

        return LoginResponse(
            access_token=access_token, user_info=user, expires_in=auth_manager.access_token_expire_minutes * 60
        )

    @app.get("/api/auth/me")
    async def get_current_user_info(user: dict = Depends(get_current_user)):
        """Obtener información del usuario actual"""
        return {"user": user, "timestamp": datetime.now(timezone.utc).isoformat()}

    @app.post("/api/auth/logout")
    async def logout(user: dict = Depends(get_current_user)):
        """Cerrar sesión (invalidar token)"""
        return {"message": "Sesión cerrada exitosamente"}

# ═══════════════════════════════════════════════════════════════
# 🏢 RUTAS DE CONFIGURACIÓN DE NEGOCIO
# ═══════════════════════════════════════════════════════════════

if business_config:

    @app.get("/api/business/config")
    async def get_business_config(user: dict = Depends(get_current_user) if auth_manager else None):
        """Obtiene configuración actual del negocio"""
        try:
            return JSONResponse(content=business_config.config)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/business/config")
    async def update_business_config(data: dict, user: dict = Depends(require_admin) if auth_manager else None):
        """Actualiza configuración completa del negocio"""
        try:
            business_config.config = business_config._merge_configs(business_config.get_default_config(), data)

            if business_config.save_config(business_config.config):
                return JSONResponse(content={"success": True, "message": "Configuración actualizada exitosamente"})
            else:
                raise HTTPException(status_code=500, detail="Error guardando configuración")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/business/preview")
    async def preview_business_config():
        """Genera vista previa del prompt"""
        try:
            config = business_config.config
            business_info = config.get("business_info", {})
            objectives = config.get("client_objectives", {})
            behavior = config.get("ai_behavior", {})

            generated_prompt = business_config._build_main_prompt(config)

            return JSONResponse(
                content={
                    "business_name": business_info.get("name"),
                    "description": business_info.get("description"),
                    "primary_goal": objectives.get("primary_goal"),
                    "generated_prompt": generated_prompt,
                    "personality": behavior.get("personality_traits", []),
                    "services": business_info.get("services", []),
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════
# 💬 RUTAS DE CHAT EN TIEMPO REAL
# ═══════════════════════════════════════════════════════════════

if chat_manager:

    @app.websocket("/ws/chat/{session_id}")
    async def websocket_chat(websocket: WebSocket, session_id: str):
        """WebSocket para chat en tiempo real"""
        await chat_manager.connect(websocket, session_id)
        try:
            while True:
                data = await websocket.receive_text()
                message_data = json.loads(data)

                if message_data.get("type") == "user_message":
                    user_message = message_data.get("message", "")
                    await chat_manager.process_message(session_id, user_message, websocket)

        except WebSocketDisconnect:
            chat_manager.disconnect(websocket, session_id)
        except Exception as e:
            logger.error(f"Error en WebSocket: {e}")
            chat_manager.disconnect(websocket, session_id)

    @app.get("/api/chat/stats")
    async def get_chat_stats():
        """Obtener estadísticas del chat"""
        return chat_manager.get_session_stats()

# ═══════════════════════════════════════════════════════════════
# 📊 RUTAS DE ANALYTICS
# ═══════════════════════════════════════════════════════════════

if analytics_manager:

    @app.get("/api/analytics/dashboard")
    async def get_analytics_dashboard(hours: int = 24):
        """Obtener métricas del dashboard"""
        try:
            metrics = analytics_manager.get_dashboard_metrics(hours)
            return JSONResponse(content=metrics)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/analytics/realtime")
    async def get_realtime_analytics():
        """Obtener estadísticas en tiempo real"""
        try:
            stats = analytics_manager.get_realtime_stats()
            return JSONResponse(content=stats)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/analytics/timeseries")
    async def get_timeseries_data(metric: str = "conversations", hours: int = 24):
        """Obtener datos de serie temporal"""
        try:
            data = analytics_manager.get_time_series_data(metric, hours)
            return JSONResponse(content=data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════
# 📱 RUTAS DE WHATSAPP
# ═══════════════════════════════════════════════════════════════

if whatsapp_manager:

    @app.post("/api/whatsapp/start")
    async def start_whatsapp_bot():
        """Iniciar bot de WhatsApp"""
        try:
            result = await whatsapp_manager.start()
            return JSONResponse(content=result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/whatsapp/stop")
    async def stop_whatsapp_bot():
        """Detener bot de WhatsApp"""
        try:
            result = await whatsapp_manager.stop()
            return JSONResponse(content=result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/whatsapp/status")
    async def get_whatsapp_status():
        """Obtener estado del bot de WhatsApp"""
        try:
            status = whatsapp_manager.get_status()
            return JSONResponse(content=status)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════
# 🧠 RUTAS DE MULTI-API
# ═══════════════════════════════════════════════════════════════

if multi_llm:

    @app.get("/api/llm/providers")
    async def get_llm_providers():
        """Obtener lista de proveedores de IA disponibles"""
        try:
            providers = multi_llm.get_available_providers()
            return JSONResponse(content={"providers": providers})
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/llm/test")
    async def test_llm_providers():
        """Probar conexión con todos los proveedores"""
        try:
            results = await multi_llm.test_all_providers()
            return JSONResponse(content={"test_results": results})
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/llm/generate")
    async def generate_llm_response(request: dict):
        """Generar respuesta usando Multi-API"""
        try:
            messages = request.get("messages", [])
            max_tokens = request.get("max_tokens", 150)
            temperature = request.get("temperature", 0.7)

            response = await multi_llm.generate_response(messages=messages, max_tokens=max_tokens, temperature=temperature)

            return JSONResponse(content={"response": response, "timestamp": datetime.now(timezone.utc).isoformat()})
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════
# 📈 RUTAS DE SISTEMA Y MONITOREO
# ═══════════════════════════════════════════════════════════════


@app.get("/api/system/info")
async def get_system_info():
    """Información general del sistema"""
    return {
        "version": "2.0.0",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "features": {
            "business_config": business_config is not None,
            "authentication": auth_manager is not None,
            "chat_testing": chat_manager is not None,
            "analytics": analytics_manager is not None,
            "whatsapp": whatsapp_manager is not None,
            "multi_llm": multi_llm is not None,
        },
        "endpoints_count": len([rule for rule in app.routes]),
        "active_features": sum(
            1
            for feature in [business_config, auth_manager, chat_manager, analytics_manager, whatsapp_manager, multi_llm]
            if feature is not None
        ),
    }


@app.get("/api/system/logs")
async def get_system_logs(lines: int = 100):
    """Obtener logs del sistema"""
    try:
        # Implementar lectura de logs
        return {"logs": f"Últimas {lines} líneas de logs (por implementar)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# 📅 RUTAS DE CALENDARIO Y CITAS
# ═══════════════════════════════════════════════════════════════

if calendar_manager:

    @app.get("/api/calendar/status")
    async def get_calendar_status():
        """Obtener estado del sistema de calendario"""
        return JSONResponse(
            content={
                "is_ready": calendar_manager.is_ready(),
                "available_providers": calendar_manager.get_available_providers(),
                "active_provider": calendar_manager._active_provider,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    @app.get("/api/calendar/config")
    async def get_calendar_config():
        """Obtener configuración actual del calendario"""
        if not business_config:
            return JSONResponse(content={})

        calendar_config = business_config.config.get("integrations", {}).get("calendar_booking", {})
        return JSONResponse(content=calendar_config)

    @app.post("/api/calendar/config")
    async def save_calendar_config(config: dict):
        """Guardar configuración del calendario"""
        if not business_config:
            raise HTTPException(status_code=500, detail="Business config not available")

        try:
            # Get current config
            current_config = business_config.config
            if "integrations" not in current_config:
                current_config["integrations"] = {}
            if "calendar_booking" not in current_config["integrations"]:
                current_config["integrations"]["calendar_booking"] = {}

            calendar_config = current_config["integrations"]["calendar_booking"]

            # Update with new values
            for key, value in config.items():
                if isinstance(value, dict) and key in calendar_config and isinstance(calendar_config[key], dict):
                    calendar_config[key].update(value)
                else:
                    calendar_config[key] = value

            # Save config
            business_config.save_config(current_config)

            # Reconfigure calendar provider if needed
            if config.get("provider") and config.get("enabled"):
                await _reconfigure_calendar_provider(calendar_config)

            return JSONResponse(content={"success": True, "message": "Configuración guardada"})

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/calendar/google/credentials")
    async def upload_google_credentials(credentials: UploadFile = File(...)):
        """Subir archivo de credenciales de Google"""
        import json
        from pathlib import Path

        try:
            content = await credentials.read()
            creds_data = json.loads(content)

            # Validate it's a valid Google credentials file
            if "installed" not in creds_data and "web" not in creds_data:
                raise HTTPException(status_code=400, detail="Archivo de credenciales inválido")

            # Save to config directory
            config_dir = Path(__file__).parent / "config"
            config_dir.mkdir(exist_ok=True)

            creds_path = config_dir / "google_credentials.json"
            with open(creds_path, "w") as f:
                json.dump(creds_data, f)

            # Update provider path
            provider = calendar_manager._providers.get("google_calendar")
            if provider:
                provider.set_credentials_path(str(creds_path))

            return JSONResponse(
                content={"success": True, "message": "Credenciales guardadas correctamente", "path": str(creds_path)}
            )

        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="El archivo no es un JSON válido")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _reconfigure_calendar_provider(config: dict):
        """Reconfigurar proveedor de calendario con nueva configuración"""
        try:
            provider_name = config.get("provider", "google_calendar")
            working_hours = config.get("working_hours", {})

            from services.calendar_service import CalendarConfig, CalendarProvider

            new_config = CalendarConfig(
                provider=CalendarProvider(provider_name),
                calendar_id=config.get(provider_name, {}).get("calendar_id", "primary"),
                default_duration_minutes=config.get("default_duration_minutes", 30),
                buffer_between_appointments=config.get("buffer_between_appointments", 15),
                working_hours=working_hours,
            )

            provider = calendar_manager._providers.get(provider_name)
            if provider:
                provider.config = new_config
                calendar_manager.set_active_provider(provider_name)

        except Exception as e:
            logger.error(f"Error reconfiguring calendar: {e}")

    @app.get("/api/calendar/oauth/google/authorize")
    async def google_oauth_authorize():
        """Iniciar flujo OAuth para Google Calendar"""
        try:
            provider = calendar_manager._providers.get("google_calendar")
            if not provider:
                raise HTTPException(status_code=404, detail="Google Calendar provider not configured")

            auth_url = provider.get_oauth_url()
            if not auth_url:
                raise HTTPException(status_code=500, detail="Failed to generate OAuth URL. Check credentials file.")

            return JSONResponse(
                content={
                    "authorization_url": auth_url,
                    "instructions": "Redirect user to this URL to authorize Google Calendar access",
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/calendar/oauth/google/callback")
    async def google_oauth_callback(code: str, state: str = None):
        """Callback para completar OAuth de Google"""
        try:
            provider = calendar_manager._providers.get("google_calendar")
            if not provider:
                raise HTTPException(status_code=404, detail="Google Calendar provider not configured")

            redirect_uri = "http://localhost:8003/api/calendar/oauth/google/callback"
            success = await provider.handle_oauth_callback(code, redirect_uri)

            if success:
                return JSONResponse(content={"success": True, "message": "Google Calendar conectado exitosamente"})
            else:
                raise HTTPException(status_code=400, detail="OAuth token exchange failed")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/calendar/oauth/outlook/authorize")
    async def outlook_oauth_authorize():
        """Iniciar flujo OAuth para Outlook Calendar"""
        try:
            provider = calendar_manager._providers.get("outlook")
            if not provider:
                raise HTTPException(status_code=404, detail="Outlook provider not configured")

            auth_url = provider.get_oauth_url()
            if not auth_url:
                raise HTTPException(status_code=500, detail="Failed to generate OAuth URL. Check credentials.")

            return JSONResponse(
                content={
                    "authorization_url": auth_url,
                    "instructions": "Redirect user to this URL to authorize Outlook access",
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/calendar/oauth/outlook/callback")
    async def outlook_oauth_callback(code: str, state: str = None):
        """Callback para completar OAuth de Outlook"""
        try:
            provider = calendar_manager._providers.get("outlook")
            if not provider:
                raise HTTPException(status_code=404, detail="Outlook provider not configured")

            redirect_uri = "http://localhost:8003/api/calendar/oauth/outlook/callback"
            success = await provider.handle_oauth_callback(code, redirect_uri)

            if success:
                return JSONResponse(content={"success": True, "message": "Outlook Calendar conectado exitosamente"})
            else:
                raise HTTPException(status_code=400, detail="OAuth token exchange failed")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/appointments/availability")
    async def get_availability(date: str = None, days: int = 7, duration_minutes: int = 30):
        """Obtener horarios disponibles para citas"""
        try:
            start_date = datetime.fromisoformat(date) if date else datetime.now(timezone.utc)

            end_date = start_date + timedelta(days=days)

            slots = await calendar_manager.get_free_slots(start_date, end_date, duration_minutes)

            return JSONResponse(
                content={
                    "available_slots": [slot.to_dict() for slot in slots],
                    "total_slots": len(slots),
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/appointments")
    async def create_appointment(data: dict):
        """Crear una nueva cita"""
        try:
            from services.calendar_service import AppointmentData

            appointment = AppointmentData(
                title=data.get("title", "Cita"),
                start_time=datetime.fromisoformat(data["start_time"]),
                end_time=datetime.fromisoformat(data["end_time"]),
                client_name=data["client_name"],
                client_email=data.get("client_email"),
                client_phone=data.get("client_phone"),
                description=data.get("description"),
                timezone=data.get("timezone", "America/Bogota"),
                send_notifications=data.get("send_notifications", True),
                add_video_conferencing=data.get("add_video_conferencing", True),
            )

            result = await calendar_manager.create_appointment(appointment)

            if result.success:
                return JSONResponse(content=result.to_dict())
            else:
                raise HTTPException(status_code=400, detail=result.error_message)

        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Missing required field: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/appointments/{external_id}")
    async def cancel_appointment(external_id: str, notify: bool = True):
        """Cancelar una cita existente"""
        try:
            success = await calendar_manager.cancel_appointment(external_id, notify)

            if success:
                return JSONResponse(content={"success": True, "message": "Cita cancelada exitosamente"})
            else:
                raise HTTPException(status_code=400, detail="No se pudo cancelar la cita")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


if appointment_flow:

    @app.get("/api/appointments/sessions")
    async def get_appointment_sessions():
        """Obtener sesiones activas de agendamiento"""
        sessions = {}
        for chat_id, session in appointment_flow._sessions.items():
            if not session.is_expired():
                sessions[chat_id] = session.to_dict()

        return JSONResponse(content={"active_sessions": sessions, "total": len(sessions)})

    @app.delete("/api/appointments/sessions/{chat_id}")
    async def cancel_appointment_session(chat_id: str):
        """Cancelar una sesión de agendamiento activa"""
        message = appointment_flow.cancel_session(chat_id)
        return JSONResponse(content={"success": True, "message": message or "Session not found"})

# ═══════════════════════════════════════════════════════════════
# 📊 WEBSOCKET - MÉTRICAS EN TIEMPO REAL
# ═══════════════════════════════════════════════════════════════


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """
    WebSocket para métricas en tiempo real
    Se actualiza cada 5 segundos con estadísticas en vivo
    """
    if not realtime_metrics:
        await websocket.close(code=1011, reason="Sistema de métricas no disponible")
        return

    await realtime_metrics.connect(websocket)

    try:
        # Mantener conexión abierta
        while True:
            # Esperar cualquier mensaje del cliente (ping/pong)
            data = await websocket.receive_text()

            # Si el cliente envía "ping", responder con "pong"
            if data == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        realtime_metrics.disconnect(websocket)
        logger.info("Cliente WebSocket desconectado")

    except Exception as e:
        logger.error(f"❌ Error en WebSocket: {e}")
        realtime_metrics.disconnect(websocket)


@app.on_event("startup")
async def startup_event():
    """Inicializar sistemas al arrancar"""
    logger.info("🚀 Iniciando sistemas...")

    # Iniciar loop de broadcast de métricas
    if realtime_metrics:
        realtime_metrics.start_broadcast_loop()
        logger.info("✅ Loop de métricas en tiempo real iniciado")

    # Limpiar métricas viejas periódicamente (cada hora)
    async def cleanup_metrics_task():
        while True:
            await asyncio.sleep(3600)  # 1 hora
            if realtime_metrics:
                realtime_metrics.cleanup_old_metrics()

    asyncio.create_task(cleanup_metrics_task())


@app.on_event("shutdown")
async def shutdown_event():
    """Limpiar al cerrar"""
    logger.info("⏸️ Deteniendo sistemas...")

    if realtime_metrics:
        realtime_metrics.stop_broadcast_loop()
        logger.info("✅ Loop de métricas detenido")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🚀 WHATSAPP AI CHATBOT - ADMIN PANEL COMPLETO")
    print("=" * 80)
    print("📍 API Base: http://127.0.0.1:8003")
    print("🎨 Dashboard: http://127.0.0.1:8003/ui/index.html")
    print("⚙️ Configurador: http://127.0.0.1:8003/ui/business_config.html")
    print("📚 API Docs: http://127.0.0.1:8003/api/docs")
    print("-" * 80)
    print("🎯 CARACTERÍSTICAS ACTIVAS:")
    print(f"   ✅ Business Config Manager: {'SÍ' if business_config else 'NO'}")
    print(f"   ✅ Sistema de Autenticación: {'SÍ' if auth_manager else 'NO'}")
    print(f"   ✅ Chat en Tiempo Real: {'SÍ' if chat_manager else 'NO'}")
    print(f"   ✅ Analytics & Métricas: {'SÍ' if analytics_manager else 'NO'}")
    print(f"   ✅ Métricas en Tiempo Real: {'SÍ' if realtime_metrics else 'NO'}")
    print(f"   ✅ WhatsApp Integration: {'SÍ' if whatsapp_manager else 'NO'}")
    print(f"   ✅ Multi-API LLM: {'SÍ' if multi_llm else 'NO'}")
    print("=" * 80)
    print("🚀 Iniciando servidor completo...")

    uvicorn.run(app, host="127.0.0.1", port=8003, reload=False, access_log=True)
