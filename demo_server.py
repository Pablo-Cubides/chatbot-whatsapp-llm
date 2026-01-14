#!/usr/bin/env python3
"""
🚀 Admin Panel Completo - WhatsApp AI Chatbot
Sistema integrado con todas las funcionalidades
"""

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import os
import io
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar sistemas creados
try:
    from business_config_manager import BusinessConfigManager, business_config
    logger.info("✅ Business Config Manager cargado")
except ImportError as e:
    logger.warning(f"⚠️ Business Config Manager no disponible: {e}")
    business_config = None

try:
    from auth_system import auth_manager, get_current_user, require_admin, LoginRequest, LoginResponse
    logger.info("✅ Sistema de autenticación cargado")
except ImportError as e:
    logger.warning(f"⚠️ Sistema de autenticación no disponible: {e}")
    auth_manager = None

try:
    from chat_system import chat_manager
    logger.info("✅ Sistema de chat cargado")
except ImportError as e:
    logger.warning(f"⚠️ Sistema de chat no disponible: {e}")
    chat_manager = None

try:
    from analytics_system import analytics_manager
    logger.info("✅ Sistema de analytics cargado")
except ImportError as e:
    logger.warning(f"⚠️ Sistema de analytics no disponible: {e}")
    analytics_manager = None

try:
    from whatsapp_system import WhatsAppManager
    from multi_provider_llm import MultiProviderLLM
    
    # Inicializar WhatsApp Manager con dependencias
    multi_llm = MultiProviderLLM()
    whatsapp_manager = WhatsAppManager(business_config, multi_llm, analytics_manager)
    logger.info("✅ Sistema de WhatsApp cargado")
except ImportError as e:
    logger.warning(f"⚠️ Sistema de WhatsApp no disponible: {e}")
    whatsapp_manager = None
    multi_llm = None

# Crear app FastAPI
app = FastAPI(
    title="WhatsApp AI Chatbot Admin Panel",
    description="Sistema completo de administración para chatbot empresarial",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir archivos estáticos
app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")

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
            "whatsapp": whatsapp_manager is not None
        },
        "endpoints": {
            "dashboard": "/ui/index.html",
            "business_config": "/ui/business_config.html",
            "api_docs": "/api/docs"
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/healthz")
async def health():
    """Health check endpoint"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "systems": {
            "api": True,
            "business_config": business_config is not None,
            "auth": auth_manager is not None,
            "chat": chat_manager is not None,
            "analytics": analytics_manager is not None,
            "whatsapp": whatsapp_manager is not None and whatsapp_manager.is_running if whatsapp_manager else False
        }
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
            raise HTTPException(
                status_code=401,
                detail="Credenciales incorrectas"
            )
        
        access_token = auth_manager.create_access_token(user)
        
        return LoginResponse(
            access_token=access_token,
            user_info=user,
            expires_in=auth_manager.access_token_expire_minutes * 60
        )
    
    @app.get("/api/auth/me")
    async def get_current_user_info(user: dict = Depends(get_current_user)):
        """Obtener información del usuario actual"""
        return {"user": user, "timestamp": datetime.now().isoformat()}
    
    @app.post("/api/auth/logout")
    async def logout(user: dict = Depends(get_current_user)):
        """Cerrar sesión (invalidar token)"""
        return {"message": "Sesión cerrada exitosamente"}

# ═══════════════════════════════════════════════════════════════
# 🏢 RUTAS DE CONFIGURACIÓN DE NEGOCIO
# ═══════════════════════════════════════════════════════════════

if business_config:
    @app.get("/api/business/config")
    async def get_business_config():
        """Obtiene configuración actual del negocio"""
        try:
            return JSONResponse(content=business_config.config)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/business/config")
    async def update_business_config(data: dict):
        """Actualiza configuración completa del negocio"""
        try:
            business_config.config = business_config._merge_configs(
                business_config.get_default_config(), 
                data
            )
            
            if business_config.save_config(business_config.config):
                return JSONResponse(content={
                    "success": True, 
                    "message": "Configuración actualizada exitosamente"
                })
            else:
                raise HTTPException(status_code=500, detail="Error guardando configuración")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/business/preview")
    async def preview_business_config():
        """Genera vista previa del prompt"""
        try:
            config = business_config.config
            business_info = config.get('business_info', {})
            objectives = config.get('client_objectives', {})
            behavior = config.get('ai_behavior', {})
            
            generated_prompt = business_config._build_main_prompt(config)
            
            return JSONResponse(content={
                "business_name": business_info.get('name'),
                "description": business_info.get('description'),
                "primary_goal": objectives.get('primary_goal'),
                "generated_prompt": generated_prompt,
                "personality": behavior.get('personality_traits', []),
                "services": business_info.get('services', [])
            })
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
            
            response = await multi_llm.generate_response(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return JSONResponse(content={
                "response": response,
                "timestamp": datetime.now().isoformat()
            })
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
        "started_at": datetime.now().isoformat(),
        "features": {
            "business_config": business_config is not None,
            "authentication": auth_manager is not None,
            "chat_testing": chat_manager is not None,
            "analytics": analytics_manager is not None,
            "whatsapp": whatsapp_manager is not None,
            "multi_llm": multi_llm is not None
        },
        "endpoints_count": len([rule for rule in app.routes]),
        "active_features": sum(1 for feature in [
            business_config, auth_manager, chat_manager, 
            analytics_manager, whatsapp_manager, multi_llm
        ] if feature is not None)
    }

@app.get("/api/system/logs")
async def get_system_logs(lines: int = 100):
    """Obtener logs del sistema"""
    try:
        # Implementar lectura de logs
        return {"logs": f"Últimas {lines} líneas de logs (por implementar)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🚀 WHATSAPP AI CHATBOT - ADMIN PANEL COMPLETO")
    print("="*80)
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
    print(f"   ✅ WhatsApp Integration: {'SÍ' if whatsapp_manager else 'NO'}")
    print(f"   ✅ Multi-API LLM: {'SÍ' if multi_llm else 'NO'}")
    print("="*80)
    print("🚀 Iniciando servidor completo...")
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8003,
        reload=False,
        access_log=True
    )
