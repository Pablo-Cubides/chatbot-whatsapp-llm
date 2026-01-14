#!/usr/bin/env python3
"""
Launcher simplificado para el admin panel con manejo de errores
"""

try:
    print("🚀 Iniciando Admin Panel...")
    
    # Importaciones básicas
    print("📦 Cargando dependencias...")
    
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    
    print("✅ FastAPI cargado")
    
    # Intentar cargar business config manager
    try:
        from business_config_manager import BusinessConfigManager, business_config
        print("✅ Business Config Manager cargado")
    except Exception as e:
        print(f"⚠️ Error cargando Business Config: {e}")
        business_config = None
    
    # Crear app FastAPI
    app = FastAPI(
        title="WhatsApp AI Chatbot Admin",
        description="Panel de administración para chatbot empresarial",
        version="1.0.0"
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
    
    @app.get("/")
    async def home():
        return {"message": "WhatsApp AI Chatbot Admin Panel", "status": "running"}
    
    @app.get("/healthz")
    async def health():
        return {"status": "healthy", "timestamp": "2026-01-13"}
    
    # Rutas de configuración (si está disponible)
    if business_config:
        @app.get("/api/business/config")
        async def get_business_config():
            try:
                return JSONResponse(content=business_config.config)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.post("/api/business/config")
        async def update_business_config(data: dict):
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
            try:
                config = business_config.config
                business_info = config.get('business_info', {})
                client_objectives = config.get('client_objectives', {})
                ai_behavior = config.get('ai_behavior', {})
                
                preview_prompt = business_config._build_main_prompt(config)
                
                return JSONResponse(content={
                    "business_name": business_info.get('name'),
                    "description": business_info.get('description'),
                    "primary_goal": client_objectives.get('primary_goal'),
                    "generated_prompt": preview_prompt,
                    "personality": ai_behavior.get('personality_traits', []),
                    "services": business_info.get('services', [])
                })
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    
    else:
        @app.get("/api/business/config")
        async def get_business_config_fallback():
            return {"error": "Business Config Manager no disponible"}
    
    if __name__ == "__main__":
        import uvicorn
        print("\n" + "="*60)
        print("🤖 WhatsApp AI Chatbot - Admin Panel")
        print("="*60)
        print("📍 Panel: http://127.0.0.1:8003")
        print("🎨 Dashboard: http://127.0.0.1:8003/ui/index.html")
        print("⚙️ Configurador: http://127.0.0.1:8003/ui/business_config.html")
        print("="*60)
        
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8003,
            reload=False,
            access_log=True
        )

except Exception as e:
    print(f"💥 Error fatal: {e}")
    import traceback
    traceback.print_exc()
    input("Presiona Enter para continuar...")
