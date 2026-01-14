from fastapi import FastAPI, Depends, HTTPException, Header, Request, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import requests
import subprocess
import json
import os
import io
import asyncio
import logging
from datetime import datetime

# Setup logger
logger = logging.getLogger(__name__)

from admin_db import initialize_schema, get_session
from sqlalchemy import text
from models import ModelConfig, Rule, AllowedContact, UserContext, DailyContext, Contact, ChatProfile, ChatCounter
import chat_sessions
import stub_chat
from string import Template as StrTemplate
from fastapi.staticfiles import StaticFiles
from reasoner import update_chat_context_and_profile
from multi_provider_llm import MultiProviderLLM, APIConfig
from business_config_manager import BusinessConfigManager, business_config

# Import psutil with fallback
try:
    import psutil
except ImportError:
    psutil = None

# Import auth dependencies
from src.services.auth_system import auth_manager, security, get_current_user, require_admin
from src.services.audit_system import audit_manager, log_login, log_logout, log_bulk_send, log_config_change
from src.services.queue_system import queue_manager
from src.services.alert_system import alert_manager
from src.services.whatsapp_provider import get_provider
from src.services.whatsapp_cloud_provider import verify_webhook

def ensure_bot_disabled_by_default():
    """Ensure respond_to_all is false by default on startup"""
    settings_file = os.path.join(os.path.dirname(__file__), 'data', 'settings.json')
    try:
        if os.path.exists(settings_file):
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        else:
            settings = {}
        
        # Force respond_to_all to false on startup unless explicitly configured
        if 'respond_to_all' not in settings:
            settings['respond_to_all'] = False
            
        # Save the settings
        os.makedirs(os.path.dirname(settings_file), exist_ok=True)
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        
        print(f"Bot auto-responder set to: {settings['respond_to_all']}")
    except Exception as e:
        print(f"Error ensuring bot disabled by default: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    initialize_schema()
    ensure_bot_disabled_by_default()
    yield
    # Shutdown
    pass


app = FastAPI(title="Chatbot Admin Panel", lifespan=lifespan)

# Enable permissive CORS for local UI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount simple static UI
ui_path = os.path.join(os.path.dirname(__file__), 'web_ui')
if os.path.isdir(ui_path):
    app.mount('/ui', StaticFiles(directory=ui_path), name='ui')


def verify_token(authorization: str = Header(None)):
    """Simple token authentication - replace with JWT in production"""
    if not authorization or authorization != "Bearer admintoken":
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return "admin"


class ModelIn(BaseModel):
    name: str
    provider: str
    model_type: Optional[str] = 'local'  # 'local' or 'online'
    config: Optional[dict] = None
    active: Optional[bool] = True


# Health and root endpoints (don't require auth)
@app.get("/", response_class=JSONResponse)
def root():
    return {"status": "ok", "app": "admin-panel", "version": "1.0"}


@app.get("/healthz", response_class=JSONResponse)
def health():
    # basic DB touch to ensure engine works
    try:
        session = get_session()
        session.execute(text("SELECT 1"))
        session.close()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/favicon.ico")
def favicon():
    """Return a simple favicon response"""
    from fastapi.responses import Response
    # Simple 1x1 transparent PNG
    favicon_bytes = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D, 
        0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4, 0x89, 0x00, 0x00, 0x00, 
        0x0A, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00, 
        0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49, 
        0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
    ])
    return Response(content=favicon_bytes, media_type="image/png")


@app.post("/models", response_model=dict)
def create_model(payload: ModelIn, user=Depends(verify_token)):
    session = get_session()
    try:
        # If a model with this name already exists, return it instead of creating a duplicate
        existing = session.query(ModelConfig).filter(ModelConfig.name == payload.name).first()
        if existing:
            return {"id": existing.id, "name": existing.name}

        m = ModelConfig(name=payload.name, provider=payload.provider, config=payload.config, active=payload.active)
        session.add(m)
        session.commit()
        session.refresh(m)
        return {"id": m.id, "name": m.name}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create model: {e}")
    finally:
        session.close()


@app.get("/models", response_model=List[dict])
def list_models(model_type: Optional[str] = None, user=Depends(verify_token)):
    session = get_session()
    query = session.query(ModelConfig)
    if model_type:
        query = query.filter(ModelConfig.model_type == model_type)
    items = query.all()
    session.close()
    return [{"id": i.id, "name": i.name, "provider": i.provider, "model_type": getattr(i, 'model_type', 'local'), "active": i.active} for i in items]


class RuleIn(BaseModel):
    name: str
    every_n_messages: int
    model_id: int
    enabled: Optional[bool] = True


@app.post("/rules")
def create_rule(payload: RuleIn, user=Depends(verify_token)):
    session = get_session()
    r = Rule(name=payload.name, every_n_messages=payload.every_n_messages, model_id=payload.model_id, enabled=payload.enabled)
    session.add(r)
    session.commit()
    session.refresh(r)
    session.close()
    return {"id": r.id}


class ContactIn(BaseModel):
    contact_id: str
    label: Optional[str]


@app.post("/contacts")
def add_contact(payload: ContactIn, user=Depends(verify_token)):
    session = get_session()
    try:
        # Upsert contact
        contact = session.query(Contact).filter(Contact.chat_id == payload.contact_id).first()
        if contact is None:
            # Create new contact with constructor parameters
            contact = Contact()
            # Use setattr to bypass type checking issues
            setattr(contact, 'chat_id', payload.contact_id)
            setattr(contact, 'name', payload.label or None)
            session.add(contact)
        else:
            if payload.label:
                setattr(contact, 'name', payload.label)
        session.commit()
        return {"chat_id": getattr(contact, 'chat_id'), "name": getattr(contact, 'name')}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
    uc = UserContext(user_id=payload.user_id, text=payload.text, source=payload.source)
    session.add(uc)
    session.commit()
    session.refresh(uc)
    session.close()
    return {"id": uc.id}

@app.get("/user-contexts/{user_id}")
def get_user_contexts(user_id: str, user=Depends(verify_token)):
    session = get_session()
    items = session.query(UserContext).filter(UserContext.user_id == user_id).all()
    session.close()
    return [{"id": i.id, "text": i.text, "source": i.source, "created_at": i.created_at} for i in items]


# --- Dashboard redirect endpoint for easier access ---
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_redirect():
    """Redirect to the main dashboard UI"""
    return HTMLResponse('<script>window.location.href="/ui/index.html"</script>')


# --- Minimal web chat UI -------------------------------------------------
@app.get("/chat", response_class=HTMLResponse)
def chat_ui():
        html = """
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8" />
            <title>Chatbot - Admin Chat</title>
            <style>
                body { font-family: Arial, Helvetica, sans-serif; margin: 20px }
                #log { border: 1px solid #ddd; padding: 10px; height: 60vh; overflow:auto; }
                .msg.user { color: #004085; }
                .msg.bot { color: #0b6623; }
                #input { width: 80%; }
            </style>
        </head>
        <body>
            <h2>Chatbot — Interfaz rápida</h2>
            <div id="log"></div>
            <div style="margin-top:10px">
                <input id="input" placeholder="Escribe aquí..." />
                <button id="send">Enviar</button>
            </div>
            <script>
                const log = document.getElementById('log');
                const input = document.getElementById('input');
                const send = document.getElementById('send');
                const CHAT_ID = 'local_web_user';

                function append(role, text){
                    const d = document.createElement('div');
                    d.className = 'msg ' + (role==='user'?'user':'bot');
                    d.textContent = (role==='user'? 'Tú: ' : 'Bot: ') + text;
                    log.appendChild(d);
                    log.scrollTop = log.scrollHeight;
                }

                send.addEventListener('click', async ()=>{
                    const v = input.value.trim(); if(!v) return;
                    append('user', v);
                    input.value = '';
                    try{
                        const r = await fetch('/api/chat', {
                            method:'POST', headers:{'Content-Type':'application/json'},
                            body: JSON.stringify({chat_id: CHAT_ID, message: v})
                        });
                        const j = await r.json();
                        append('bot', j.reply || '(sin respuesta)');
                    } catch(e){ append('bot','(error contactando al servidor)'); }
                });

                input.addEventListener('keydown', (e)=>{ if(e.key==='Enter') send.click(); });
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html, status_code=200)


# --- Dashboard API endpoints for web UI ----------------------------------

def _lm_port() -> int:
    try:
        return int(os.environ.get('LM_STUDIO_PORT', '1234'))
    except Exception:
        return 1234


def _kill_processes(matchers):
    """Terminate processes whose name or cmdline contains any matcher.
    Returns list of killed PIDs.
    """
    killed = []
    if psutil is None:
        return killed
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = (proc.info.get('name') or '').lower()
            cmdline = ' '.join(proc.info.get('cmdline') or []).lower()
            if any(m.lower() in name or m.lower() in cmdline for m in matchers):
                proc.terminate()
                killed.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    # best-effort wait and force-kill
    try:
        psutil.wait_procs([psutil.Process(pid) for pid in killed if psutil.pid_exists(pid)], timeout=2)
    except Exception:
        pass
    for pid in list(killed):
        try:
            if psutil.pid_exists(pid):
                psutil.Process(pid).kill()
        except Exception:
            pass
    return killed

def _kill_processes_except_current(matchers, exclude_pid):
    """Terminate processes whose name or cmdline contains any matcher, EXCEPT exclude_pid.
    Returns list of killed PIDs.
    """
    killed = []
    if psutil is None:
        return killed
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Skip the current admin panel process
            if proc.info['pid'] == exclude_pid:
                continue
                
            name = (proc.info.get('name') or '').lower()
            cmdline = ' '.join(proc.info.get('cmdline') or []).lower()
            if any(m.lower() in name or m.lower() in cmdline for m in matchers):
                proc.terminate()
                killed.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    # best-effort wait and force-kill
    try:
        psutil.wait_procs([psutil.Process(pid) for pid in killed if psutil.pid_exists(pid)], timeout=2)
    except Exception:
        pass
    for pid in list(killed):
        try:
            if psutil.pid_exists(pid):
                psutil.Process(pid).kill()
        except Exception:
            pass
    return killed

def _kill_by_port(port: int) -> list:
    """Kill processes listening on a given TCP port (best-effort)."""
    killed = []
    if psutil is None:
        return killed
    try:
        for proc in psutil.process_iter(['pid', 'name', 'connections']):
            try:
                conns = proc.connections(kind='inet') if hasattr(proc, 'connections') else []
                for c in conns:
                    try:
                        if c.laddr and getattr(c.laddr, 'port', None) == port:
                            proc.terminate()
                            killed.append(proc.pid)
                            break
                    except Exception:
                        continue
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        # wait then force
        try:
            psutil.wait_procs([psutil.Process(pid) for pid in killed if psutil.pid_exists(pid)], timeout=2)
        except Exception:
            pass
        for pid in list(killed):
            try:
                if psutil.pid_exists(pid):
                    psutil.Process(pid).kill()
            except Exception:
                pass
    except Exception:
        pass
    return list(set(killed))

def _script_match_in_cmdline(proc, script_name: str) -> bool:
    """Return True if the given process' cmdline references the script (by name or absolute path)."""
    try:
        parts = proc.info.get('cmdline') or []
        if not parts:
            return False
        cmd = ' '.join(str(x) for x in parts)
        cmd_low = cmd.lower().replace('\\', '/')
        # Direct name match
        if script_name.lower() in cmd_low:
            return True
        # Absolute path match
        here = os.path.dirname(__file__)
        abs_path = os.path.join(here, script_name).replace('\\', '/').lower()
        return abs_path in cmd_low
    except Exception:
        return False

def _get_playwright_profile_dir() -> str:
    """Read Playwright userDataDir from config/playwright_config.json if available."""
    try:
        cfg_path = os.path.join(os.path.dirname(__file__), 'config', 'playwright_config.json')
        if not os.path.exists(cfg_path):
            return ''
        raw = open(cfg_path, 'r', encoding='utf-8').read()
        try:
            raw = StrTemplate(raw).substitute(os.environ)
        except Exception:
            pass
        import json as _json
        data = _json.loads(raw)
        return data.get('userDataDir') or ''
    except Exception:
        return ''

def _kill_browser_profile_processes() -> list:
    """Kill Chromium/Edge/Chrome processes bound to the Playwright userDataDir."""
    killed = []
    if psutil is None:
        return killed
    profile = _get_playwright_profile_dir()
    if not profile:
        return killed
    prof_norm = profile.lower().replace('\\', '/').strip()
    targets = ['chrome.exe', 'msedge.exe', 'chromium.exe', 'chrome', 'msedge', 'chromium']
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = (proc.info.get('name') or '').lower()
            cmd = ' '.join(proc.info.get('cmdline') or []).lower().replace('\\', '/')
            if any(t in name for t in targets) and (prof_norm and prof_norm in cmd):
                proc.terminate()
                killed.append(proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    try:
        psutil.wait_procs([psutil.Process(pid) for pid in killed if psutil.pid_exists(pid)], timeout=2)
    except Exception:
        pass
    for pid in list(killed):
        try:
            if psutil.pid_exists(pid):
                psutil.Process(pid).kill()
        except Exception:
            pass
    return list(set(killed))


def _filter_and_categorize_models(models):
    """Filtra y categoriza modelos según criterios específicos de Pablo"""
    
    # MODELOS PRINCIPALES PERMITIDOS (solo estos 3) - NOMBRES REALES DE LM STUDIO
    allowed_main_models = [
        'nemotron-mini-4b-instruct',
        'meta-llama-3.1-8b-instruct', 
        'phi-4'
    ]
    
    # MODELOS RAZONADORES PERMITIDOS (solo estos 2) - NOMBRES REALES DE LM STUDIO
    allowed_reasoning_models = [
        'deepseek-r1-distill-qwen-7b',
        'openai/gpt-oss-20b'
    ]
    
    # Filtrar modelos
    main_models = []
    reasoning_models = []
    hidden_models = []  # text-embedding, etc
    other_models = []   # Para función "agregar modelo"
    
    for model in models:
        model_name = model.get('id', '').lower()
        
        # Verificar si está en la lista principal permitida
        if model_name in allowed_main_models:
            main_models.append({**model, 'category': 'main'})
        
        # Verificar si está en la lista de razonadores permitidos
        elif model_name in allowed_reasoning_models:
            reasoning_models.append({**model, 'category': 'reasoning'})
        
        # Ocultar embeddings pero mantener para RAG
        elif 'embed' in model_name or 'embedding' in model_name:
            hidden_models.append({**model, 'category': 'hidden'})
        
        # Todo lo demás va a "otros" para agregar manualmente
        else:
            other_models.append({**model, 'category': 'other'})
    
    return {
        'main_models': main_models,
        'reasoning_models': reasoning_models, 
        'hidden_models': hidden_models,
        'other_models': other_models,
        'all_available': other_models + hidden_models  # Para función agregar
    }

@app.get('/api/lmstudio/models')
def api_lmstudio_models():
    """Detect models from LM Studio API con filtrado específico de Pablo.

    Returns:
    {
      status: 'success'|'error',
      lm_studio_running: bool,
      main_models: [Solo 3 modelos principales permitidos],
      reasoning_models: [Solo 2 modelos razonadores permitidos],
      available_for_add: [Modelos disponibles para agregar manualmente],
      current_model: str,
      note?: str,
      error?: str
    }
    """
    import socket
    import glob

    def _is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    # 1) Check LM Studio port
    port = _lm_port()
    lm_running = _is_port_open('127.0.0.1', port)

    models = []
    api_error = None
    if lm_running:
        try:
            resp = requests.get(f"http://127.0.0.1:{port}/v1/models", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get('data', []):
                    models.append({
                        'id': m.get('id', 'unknown'),
                        'name': m.get('id', 'unknown'),
                        'object': m.get('object', 'model'),
                        'source': 'lmstudio'
                    })
            else:
                api_error = f"LM Studio respondió {resp.status_code} en /v1/models"
        except Exception as e:
            api_error = str(e)

    # 2) Fallback: scan local GGUF models folder
    models_dir = os.environ.get('MODELS_DIR') or (r'D:\IA\Texto\Models' if os.name == 'nt' else '/mnt/d/IA/Texto/Models')
    local_models = []
    try:
        if os.path.isdir(models_dir):
            # Search recursively for .gguf files
            pattern = os.path.join(models_dir, '**', '*.gguf')
            for path in glob.iglob(pattern, recursive=True):
                name = os.path.splitext(os.path.basename(path))[0]
                local_models.append({
                    'id': name,
                    'name': name,
                    'path': path,
                    'source': 'local'
                })
    except Exception:
        # ignore local scanning errors
        pass

    # 3) Combinar todos los modelos y filtrar
    all_models = models + local_models
    categorized = _filter_and_categorize_models(all_models)
    
    # 4) Obtener modelo actual del payload.json
    current_model = "ninguno"
    try:
        payload_path = os.path.join(os.path.dirname(__file__), 'payload.json')
        with open(payload_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
            current_model = payload.get('model', 'ninguno')
    except Exception:
        pass
    
    result = {
        'status': 'success',
        'lm_studio_running': bool(lm_running),
        'main_models': categorized['main_models'],
        'reasoning_models': categorized['reasoning_models'],
        'available_for_add': categorized['all_available'],
        'current_model': current_model,
        'port': port,
    }

    if api_error and not models:
        result['status'] = 'error'
        result['error'] = api_error
        if local_models:
            result['note'] = 'LM Studio no respondió /v1/models, mostrando modelos locales encontrados.'
        else:
            result['note'] = 'LM Studio no respondió y no se encontraron modelos locales.'

    return result

@app.post('/api/lmstudio/add-model')
async def api_lmstudio_add_model(request: Request):
    """Agregar modelo manualmente a lista principal o razonadores"""
    try:
        body = await request.json()
        model_id = body.get('model_id')
        target_list = body.get('target_list', 'main')  # 'main' o 'reasoning'
        
        if not model_id:
            return {"success": False, "error": "model_id requerido"}
        
        if target_list not in ['main', 'reasoning']:
            return {"success": False, "error": "target_list debe ser 'main' o 'reasoning'"}
        
        # Obtener modelos disponibles
        models_response = api_lmstudio_models()
        available_models = models_response.get('available_for_add', [])
        
        # Verificar que el modelo está disponible
        selected_model = None
        for model in available_models:
            if model['id'] == model_id:
                selected_model = model
                break
        
        if not selected_model:
            return {"success": False, "error": f"Modelo {model_id} no disponible para agregar"}
        
        # Actualizar las listas permitidas en el código (esto requiere editar el archivo)
        # Por ahora, solo cambiar el modelo activo en payload.json
        payload_path = os.path.join(os.path.dirname(__file__), 'payload.json')
        try:
            with open(payload_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            
            old_model = payload.get('model', 'unknown')
            payload['model'] = model_id
            
            with open(payload_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
            
            return {
                "success": True, 
                "message": f"Modelo '{model_id}' agregado a lista {target_list} y activado",
                "old_model": old_model,
                "new_model": model_id,
                "target_list": target_list,
                "note": "NOTA: Para que aparezca permanentemente en la lista, contacta al desarrollador"
            }
            
        except Exception as e:
            return {"success": False, "error": f"Error actualizando payload.json: {e}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post('/api/lmstudio/switch-model')
async def api_lmstudio_switch_model(request: Request):
    """Cambiar entre modelos ya permitidos en las listas"""
    try:
        body = await request.json()
        model_id = body.get('model_id')
        
        if not model_id:
            return {"success": False, "error": "model_id requerido"}
        
        # Verificar que es un modelo permitido
        models_response = api_lmstudio_models()
        main_models = models_response.get('main_models', [])
        reasoning_models = models_response.get('reasoning_models', [])
        
        allowed_models = [m['id'] for m in main_models + reasoning_models]
        
        if model_id not in allowed_models:
            return {"success": False, "error": f"Modelo {model_id} no está en listas permitidas"}
        
        # Actualizar payload.json
        payload_path = os.path.join(os.path.dirname(__file__), 'payload.json')
        try:
            with open(payload_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            
            old_model = payload.get('model', 'unknown')
            payload['model'] = model_id
            
            with open(payload_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
            
            return {
                "success": True, 
                "message": f"Modelo cambiado de '{old_model}' a '{model_id}'",
                "old_model": old_model,
                "new_model": model_id
            }
            
        except Exception as e:
            return {"success": False, "error": f"Error actualizando payload.json: {e}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post('/api/lmstudio/start')
def api_lmstudio_start():
    """Attempt to start LM Studio app on Windows and wait for local server port.
    This looks for common install paths and launches the app; then polls port.
    """
    try:
        port = _lm_port()
    # If already running, return quickly
        import socket
        def _is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    return True
            except OSError:
                return False

        if _is_port_open('127.0.0.1', port):
            return {"success": True, "message": f"LM Studio ya está activo en {port}", "port": port}

        # Candidate executable paths on Windows
        candidates = []
        # Candidate executable paths on Windows (plus env override)
        env_exe = os.environ.get('LM_STUDIO_EXE')
        if env_exe:
            candidates.append(env_exe)
        if os.name == 'nt':
            candidates.extend([
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\LM Studio\LM Studio.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\lm-studio\LM Studio.exe"),
                os.path.expandvars(r"C:\\Program Files\\LM Studio\\LM Studio.exe"),
                os.path.expandvars(r"C:\\Program Files (x86)\\LM Studio\\LM Studio.exe"),
                # User-provided installation path(s)
                r"D:\\IA\\Texto\\Lmstudio\\LM Studio.exe",
                r"D:\\IA\\Texto\\Lmstudio",
                r"D:\\IA\\Texto\\Lmstudio\\LM Studio",
            ])

        # Normalize and check; if a candidate is a directory, look for the exe inside
        exe_path = None
        for p in candidates:
            if not p:
                continue
            # If path points to a directory, try to append the exe name
            if os.path.isdir(p):
                # Try common exe names
                for name in ['LM Studio.exe', 'lm studio.exe', 'LMStudio.exe', 'lmstudio.exe', 'LM-Studio.exe']:
                    possible = os.path.join(p, name)
                    if os.path.isfile(possible):
                        exe_path = possible
                        break
                if exe_path:
                    break
                # Fallback: scan dir (and one subdir) for any exe containing both 'lm' and 'studio'
                try:
                    for root, _dirs, files in os.walk(p):
                        for fname in files:
                            if fname.lower().endswith('.exe') and 'lm' in fname.lower() and 'studio' in fname.lower():
                                exe_path = os.path.join(root, fname)
                                break
                        if exe_path:
                            break
                except Exception:
                    pass
                if exe_path:
                    break
            # If path has no extension and exists without .exe, try with .exe
            if not os.path.splitext(p)[1]:
                with_exe = p + '.exe'
                if os.path.isfile(with_exe):
                    exe_path = with_exe
                    break
            # Direct file
            if os.path.isfile(p):
                exe_path = p
                break
        if not exe_path:
            return {"success": False, "error": "No se encontró LM Studio en rutas conocidas. Define LM_STUDIO_EXE con la ruta completa al .exe", "tried": candidates}

        # Launch the app
        try:
            subprocess.Popen([exe_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            return {"success": False, "error": f"No se pudo iniciar LM Studio: {e}"}

        # Poll the port for up to ~30s
        import time
        deadline = time.time() + 30
        while time.time() < deadline:
            if _is_port_open('127.0.0.1', port):
                return {"success": True, "message": f"LM Studio iniciado y escuchando en {port}", "port": port}
            time.sleep(1)

        return {"success": False, "error": f"LM Studio no se activó en el puerto {port} en el tiempo esperado."}
    except Exception as e:
        return {"success": False, "error": str(e)}


# --- LM Studio CLI support: start server and load model -----------------------
def _find_lms_exe() -> Optional[str]:
    """Try to locate the LM Studio CLI (lms.exe) on Windows.
    Honors LMS_EXE and LM_STUDIO_DIR env vars, searches known folders recursively.
    Returns absolute path or None if not found.
    """
    # 1) Direct override
    env_exe = os.environ.get('LMS_EXE') or os.environ.get('LM_STUDIO_CLI')
    if env_exe and os.path.isfile(env_exe):
        return env_exe

    # 2) Directory override
    search_dirs = []
    for key in ('LM_STUDIO_DIR', 'LM_STUDIO_HOME'):
        val = os.environ.get(key)
        if val and os.path.isdir(val):
            search_dirs.append(val)

    # 3) Known install paths
    if os.name == 'nt':
        search_dirs.extend([
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\LM Studio"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\lm-studio"),
            r"D:\\IA\\Texto\\Lmstudio",
            r"C:\\Program Files\\LM Studio",
            r"C:\\Program Files (x86)\\LM Studio",
        ])

    # 4) Search recursively for lms.exe
    try:
        import glob
        for base in search_dirs:
            if not os.path.isdir(base):
                continue
            for pattern in ("**/lms.exe", "**/LM Studio CLI.exe", "**/lmstudio.exe"):
                for match in glob.iglob(os.path.join(base, pattern), recursive=True):
                    if os.path.isfile(match):
                        return match
    except Exception:
        pass

    # 5) Fallback: if 'lms' is on PATH we'll just return the name and let Popen resolve it
    return 'lms'


@app.post('/api/lmstudio/server/start')
def api_lmstudio_server_start():
    """Start the LM Studio local server via CLI: `lms server start --port <port>`.
    Spawns a background process and waits until the port is open.
    """
    try:
        port = _lm_port()
        # If already up, return
        import socket
        import time
        def _is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    return True
            except OSError:
                return False

        if _is_port_open('127.0.0.1', port):
            return {"success": True, "message": f"Servidor ya activo en {port}", "port": port}

        lms = _find_lms_exe()
        if not lms:
            return {"success": False, "error": "No se encontró CLI de LM Studio (lms). Configura LMS_EXE o LM_STUDIO_DIR."}

        # Spawn server; keep it detached so it persists
        creation = subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        try:
            # Prefer app root as CWD if available
            subprocess.Popen([lms, 'server', 'start', '--port', str(port)],
                             cwd=_lm_app_cwd(lms) if os.path.isabs(lms) else None,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=creation, shell=False)
        except FileNotFoundError:
            # Try letting the shell resolve 'lms' if lms is just a name
            subprocess.Popen(f"lms server start --port {port}", shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Wait up to 30s for the port
        deadline = time.time() + 30
        while time.time() < deadline:
            if _is_port_open('127.0.0.1', port):
                return {"success": True, "message": f"Servidor iniciado en {port}", "port": port}
            time.sleep(1)
        return {"success": False, "error": f"El servidor no abrió el puerto {port} a tiempo"}
    except Exception as e:
        return {"success": False, "error": str(e)}


class LMStudioLoadRequest(BaseModel):
    model: str


@app.post('/api/lmstudio/load')
async def api_lmstudio_load(request: Request):
    """Load a model via LM Studio CLI: `lms load <model>`.
    Returns the CLI output or error message.
    """
    try:
        # Accept flexible payloads: JSON object {model}, raw JSON string, form, or query param
        model_value: Optional[str] = None
        # Try JSON
        try:
            data = await request.json()
            if isinstance(data, str):
                model_value = data
            elif isinstance(data, dict):
                model_value = data.get('model') or next((v for k, v in data.items() if str(k).lower() == 'model'), None)
        except Exception:
            pass
        # Try form
        if not model_value:
            try:
                form = await request.form()
                form_model = form.get('model')
                model_value = str(form_model) if form_model and not hasattr(form_model, 'read') else None
            except Exception:
                pass
        # Try query
        if not model_value:
            model_value = request.query_params.get('model') if hasattr(request, 'query_params') else None

        if not model_value:
            return {"success": False, "error": "Falta el parámetro 'model' en el cuerpo o la query"}

        lms = _find_lms_exe()
        if not lms:
            return {"success": False, "error": "No se encontró CLI de LM Studio (lms). Configura LMS_EXE o LM_STUDIO_DIR."}

        # Normalize model path if it's a local file
        model_arg = model_value
        try:
            if os.path.isabs(model_arg) and os.path.exists(model_arg):
                model_arg = os.path.normpath(model_arg)
        except Exception:
            pass

        # Try multiple command variants for compatibility
        trials = [
            [lms, 'load', model_arg],
            [lms, 'model', 'load', model_arg],  # More common syntax
            [lms, 'server', 'load', model_arg],  # Alternative
        ]

        combined_out = ""
        combined_err = ""
        # Prepare environment and working directory
        app_cwd = _lm_app_cwd(lms) if os.path.isabs(lms) else None
        env = os.environ.copy()
        try:
            lms_dir = os.path.dirname(lms) if os.path.isabs(lms) else None
            if lms_dir:
                env['PATH'] = f"{lms_dir};{env.get('PATH','')}"
        except Exception:
            pass

        for args in trials:
            try:
                completed = subprocess.run(args,
                                           cwd=app_cwd,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           text=True, timeout=180, shell=False, env=env)
            except FileNotFoundError:
                # Try through shell if only command name is available
                cmd = " ".join([str(a) for a in [args[0]]] + [subprocess.list2cmdline(args[1:])])
                completed = subprocess.run(cmd, shell=True,
                                           cwd=app_cwd,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           text=True, timeout=180, env=env)

            combined_out += f"\n$ {' '.join(str(a) for a in args)}\n" + (completed.stdout or "")
            combined_err += (completed.stderr or "")
            if completed.returncode == 0:
                return {"success": True, "output": combined_out[-4000:]}

        return {
            "success": False,
            "output": combined_out[-4000:],
            "error": combined_err[-4000:] or "No se pudo cargar el modelo con los comandos probados",
        }
    except Exception as e:
        # Catch-all for unexpected errors
        return {"success": False, "error": str(e)}


@app.post('/api/lmstudio/server/stop')
def api_lmstudio_server_stop():
    """Stop LM Studio server processes (CLI) best-effort."""
    try:
        killed = []
        killed += _kill_processes(['lms', 'lms.exe', 'lm-studio', 'lm studio local server'])
        # Also kill port 1234 or configured LM STUDIO port
        killed += _kill_by_port(_lm_port())
        return {"success": True, "stopped_pids": list(set(killed))}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post('/api/lmstudio/app/stop')
def api_lmstudio_app_stop():
    """Stop LM Studio GUI app best-effort."""
    try:
        killed = _kill_processes(['lm studio.exe', 'lmstudio.exe'])
        return {"success": True, "stopped_pids": killed}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get('/api/system/check-processes')
def api_system_check_processes():
    """Verificar qué procesos problemáticos están corriendo ANTES de la limpieza"""
    try:
        problematic_processes = []
        
        if psutil:
            # Procesos a verificar
            targets = [
                'LM Studio.exe', 'lms.exe', 'lmstudio.exe',
                'chrome.exe', 'chromium.exe', 'msedge.exe', 
                'python.exe', 'python3.exe', 'python3.13.exe',
                'whatsapp_automator.py'
            ]
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    cmdline = ' '.join(proc.info.get('cmdline') or []).lower()
                    
                    for target in targets:
                        if target.lower() in name or target.lower() in cmdline:
                            memory_mb = 0
                            try:
                                mem_info = proc.info.get('memory_info')
                                if mem_info:
                                    memory_mb = mem_info.rss // (1024 * 1024)
                            except Exception:
                                pass
                            
                            problematic_processes.append({
                                'pid': proc.info['pid'],
                                'name': proc.info.get('name', 'unknown'),
                                'target_match': target,
                                'memory_mb': memory_mb,
                                'cmdline_snippet': cmdline[:100] + '...' if len(cmdline) > 100 else cmdline
                            })
                            break
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        
        # Verificar puertos ocupados
        import socket
        ports_status = {}
        for port in [1234, 8000, 8001, 8002, 8003]:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                    ports_status[port] = "OCUPADO"
            except OSError:
                ports_status[port] = "LIBRE"
        
        return {
            "success": True,
            "problematic_processes": problematic_processes,
            "total_problematic": len(problematic_processes),
            "ports_status": ports_status,
            "needs_cleanup": len(problematic_processes) > 0 or any(status == "OCUPADO" for status in ports_status.values())
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post('/api/system/stop-all')
def api_system_stop_all():
    """STOP NUCLEAR: Mata TODO (LM Studio, Chrome, Python, WhatsApp automator) como hizo Pablo."""
    try:
        killed = []
        results = []
        
        # 1. Matar procesos usando psutil primero (si está disponible)
        if psutil:
            # LM Studio - todas las variantes
            lm_processes = ['LM Studio.exe', 'lms.exe', 'lms', 'lm-studio', 'lmstudio.exe']
            for process_name in lm_processes:
                pids = _kill_processes([process_name])
                if pids:
                    killed.extend(pids)
                    results.append(f"psutil: Matados {len(pids)} procesos de {process_name}")
            
            # Chrome y browsers
            browser_processes = ['chrome.exe', 'chromium.exe', 'msedge.exe']
            for process_name in browser_processes:
                pids = _kill_processes([process_name])
                if pids:
                    killed.extend(pids)
                    results.append(f"psutil: Matados {len(pids)} procesos de {process_name}")
            
            # Python - todas las versiones PERO NO EL ADMIN PANEL ACTUAL
            import os
            current_pid = os.getpid()  # PID del admin panel actual
            
            python_processes = ['python.exe', 'python3.exe', 'python3.13.exe', 'pythonw.exe']
            for process_name in python_processes:
                pids = _kill_processes_except_current([process_name], current_pid)
                if pids:
                    killed.extend(pids)
                    results.append(f"psutil: Matados {len(pids)} procesos de {process_name} (excluyendo admin panel)")
            
            # WhatsApp automator específico
            wa_pids = _kill_processes(['whatsapp_automator.py'])
            if wa_pids:
                killed.extend(wa_pids)
                results.append(f"psutil: Matados {len(wa_pids)} procesos WhatsApp automator")
        
        # 2. Usar taskkill de Windows como backup/fuerza bruta (método que funcionó)
        import subprocess
        try:
            # Comando robusto que funcionó en PowerShell (SIN matar admin panel)
            taskkill_commands = [
                'taskkill /f /im "LM Studio.exe" 2>nul',
                'taskkill /f /im lms.exe 2>nul', 
                'taskkill /f /im chrome.exe 2>nul',
                # NO matamos python.exe genéricamente porque mataría el admin panel
                'taskkill /f /im chromium.exe 2>nul',
                'taskkill /f /im msedge.exe 2>nul'
            ]
            
            for cmd in taskkill_commands:
                try:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                    if "SUCCESS" in result.stdout:
                        lines = result.stdout.count("SUCCESS")
                        results.append(f"taskkill: Matados {lines} procesos con {cmd.split()[3]}")
                except subprocess.TimeoutExpired:
                    results.append(f"taskkill: Timeout en {cmd}")
                except Exception as e:
                    results.append(f"taskkill: Error en {cmd}: {e}")
        
        except Exception as e:
            results.append(f"taskkill: Error general: {e}")
        
        # 3. Matar por puertos específicos (EXCEPTO el puerto del admin panel)
        ports_to_kill = [1234, 8000, 8001, 8002]  # LM Studio y otros admin panels, NO 8003
        for port in ports_to_kill:
            port_pids = _kill_by_port(port)
            if port_pids:
                killed.extend(port_pids)
                results.append(f"puerto: Matados {len(port_pids)} procesos en puerto {port}")
        
        # 4. Esperar un poco y verificar
        import time
        time.sleep(2)
        
        # 5. Verificar que los puertos estén libres
        import socket
        ports_status = {}
        for port in [1234, 8003]:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=1):
                    ports_status[port] = "OCUPADO ⚠️"
            except OSError:
                ports_status[port] = "LIBRE ✅"
        
        return {
            "success": True, 
            "total_killed_pids": len(set(killed)),
            "unique_killed_pids": list(set(killed)),
            "actions": results,
            "ports_status": ports_status,
            "message": f"🧹 LIMPIEZA NUCLEAR COMPLETADA - {len(set(killed))} procesos eliminados"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def _lm_app_cwd(lms_path: str) -> Optional[str]:
    """Best-effort to find the LM Studio app root for CWD.
    Walk up from lms_path to locate a folder containing 'LM Studio.exe'.
    """
    try:
        base = os.path.dirname(lms_path)
        cur = base
        for _ in range(5):
            if os.path.isfile(os.path.join(cur, 'LM Studio.exe')):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
        return base
    except Exception:
        return None


class LMStudioWarmupRequest(BaseModel):
    model: str


@app.post('/api/lmstudio/warmup')
def api_lmstudio_warmup(req: LMStudioWarmupRequest):
    """Trigger a tiny chat call to LM Studio HTTP API to force-load a model.
    Returns success when the call returns 200.
    """
    try:
        port = _lm_port()
        url = f"http://127.0.0.1:{port}/v1/chat/completions"
        payload = {
            "model": req.model,
            "messages": [{"role": "user", "content": "ok"}],
            "max_tokens": 1,
            "temperature": 0,
        }
        r = requests.post(url, json=payload, timeout=60)
        if r.status_code == 200:
            return {"success": True}
        else:
            return {"success": False, "error": f"HTTP {r.status_code}", "body": r.text[-2000:]}
    except requests.Timeout:
        return {"success": False, "error": "Tiempo de espera agotado al llamar al API"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get('/api/reasoner-model')
def api_get_reasoner_model():
    """Get current reasoner model from payload_reasoner.json"""
    try:
        payload_path = os.path.join(os.path.dirname(__file__), "payload_reasoner.json")
        with open(payload_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        return {"reasoner_model": payload.get("model", "unknown")}
    except Exception as e:
        return {"error": str(e), "reasoner_model": "unknown"}


class ReasonerModelChangeRequest(BaseModel):
    model: str


@app.put('/api/reasoner-model')
def api_set_reasoner_model(request: ReasonerModelChangeRequest):
    """Update reasoner model in payload_reasoner.json"""
    try:
        payload_path = os.path.join(os.path.dirname(__file__), "payload_reasoner.json")
        with open(payload_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        payload["model"] = request.model
        with open(payload_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
        return {"success": True, "reasoner_model": request.model}
    except Exception as e:
        return {"error": str(e), "success": False}

@app.get('/api/current-model', dependencies=[Depends(security)])
def api_get_current_model():
    """Get current model from payload.json"""
    try:
        payload_path = os.path.join(os.path.dirname(__file__), "payload.json")
        with open(payload_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        return {"current_model": payload.get("model", "unknown")}
    except Exception as e:
        return {"error": str(e), "current_model": "unknown"}

class ModelChangeRequest(BaseModel):
    model: str

@app.put('/api/current-model', dependencies=[Depends(security)])
def api_set_current_model(request: ModelChangeRequest):
    """Update current model in payload.json"""
    try:
        payload_path = os.path.join(os.path.dirname(__file__), "payload.json")
        
        # Read current payload
        with open(payload_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        
        # Update model
        payload["model"] = request.model
        
        # Write back
        with open(payload_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
        
        # Reload stub_chat module to pick up changes
        import importlib
        importlib.reload(stub_chat)
        
        return {"success": True, "new_model": request.model}
    except Exception as e:
        return {"error": str(e), "success": False}

@app.get('/api/whatsapp/status', dependencies=[Depends(security)])
def api_whatsapp_status():
    """Check if WhatsApp automator is running"""
    try:
        if psutil is None:
            return {"status": "error", "error": "psutil not available"}
            
        automator_pid = None
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if _script_match_in_cmdline(proc, 'whatsapp_automator.py'):
                    automator_pid = proc.info['pid']
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Also detect leftover browser processes tied to the Playwright profile
        browser_pids = []  # discovery only
        if not browser_pids and psutil is not None:
            profile = _get_playwright_profile_dir()
            prof_norm = profile.lower().replace('\\', '/').strip() if profile else ''
            targets = ['chrome.exe', 'msedge.exe', 'chromium.exe', 'chrome', 'msedge', 'chromium']
            for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = (p.info.get('name') or '').lower()
                    cmd = ' '.join(p.info.get('cmdline') or []).lower().replace('\\', '/')
                    if prof_norm and any(t in name for t in targets) and prof_norm in cmd:
                        browser_pids.append(p.info['pid'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        if automator_pid:
            return {"status": "running", "pid": automator_pid, "browser_pids": browser_pids}
        if browser_pids:
            return {"status": "stale-browser", "pid": None, "browser_pids": browser_pids}
        return {"status": "stopped", "pid": None, "browser_pids": []}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post('/api/whatsapp/start', dependencies=[Depends(security)])
def api_whatsapp_start():
    """Start WhatsApp automator (with LM Studio validation)"""
    try:
        # First, validate that LM Studio is ready
        lm_status = api_lmstudio_local_models()
        
        if not lm_status.get("lm_studio_running", False):
            return {
                "success": False, 
                "error": "LM Studio no está ejecutándose. Inicia el servidor en puerto 1234 antes de continuar."
            }
        
        if not lm_status.get("models") or len(lm_status.get("models", [])) == 0:
            return {
                "success": False, 
                "error": "No hay modelos cargados en LM Studio. Carga un modelo antes de iniciar WhatsApp."
            }
        
        # Check if already running
        status = api_whatsapp_status()
        if status.get("status") == "running":
            return {"success": False, "error": "WhatsApp automator already running"}
        
        # Start the automator in a new process
        script_path = os.path.join(os.path.dirname(__file__), "whatsapp_automator.py")
        venv_python = os.path.join(os.path.dirname(__file__), "venv", "Scripts", "python.exe")
        
        if os.path.exists(venv_python):
            python_cmd = venv_python
        else:
            python_cmd = "python"
        
        # Set environment variable to keep automator open
        env = os.environ.copy()
        env["KEEP_AUTOMATOR_OPEN"] = "true"
        
        # Start process in a detached manner and redirect output to a log so the reloader
        # or parent process doesn't get blocked by child stdout/stderr encoding issues.
        try:
            log_dir = os.path.join(os.path.dirname(__file__), 'logs')
            os.makedirs(log_dir, exist_ok=True)
            start_log = os.path.join(log_dir, 'whatsapp_start.log')
            stdout_f = open(start_log, 'a', encoding='utf-8')
            stderr_f = stdout_f
        except Exception:
            stdout_f = subprocess.DEVNULL
            stderr_f = subprocess.DEVNULL

        # Choose creation flags for Windows to detach
        creationflags = 0
        if os.name == 'nt':
            # DETACHED_PROCESS prevents child from inheriting console; CREATE_NEW_PROCESS_GROUP
            # allows sending CTRL events if needed.
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, 'DETACHED_PROCESS', 0)

        # Prefer the venv python if available, otherwise fall back to sys.executable
        import sys
        import time
        if not os.path.exists(python_cmd):
            python_cmd = sys.executable or python_cmd

        proc = subprocess.Popen(
            [python_cmd, script_path],
            cwd=os.path.dirname(__file__),
            env=env,
            stdout=stdout_f,
            stderr=stderr_f,
            close_fds=True,
            creationflags=creationflags
        )
        
        # Give it a moment to start
        time.sleep(1)
        
        return {"success": True, "pid": proc.pid, "message": "WhatsApp automator started"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post('/api/whatsapp/stop', dependencies=[Depends(security)])
def api_whatsapp_stop():
    """Stop WhatsApp automator"""
    try:
        if psutil is None:
            return {"success": False, "error": "psutil not available"}
            
        stopped_pids = []
        targets = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if _script_match_in_cmdline(proc, 'whatsapp_automator.py'):
                    targets.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        # Try graceful terminate first
        for p in targets:
            try:
                p.terminate()
            except Exception:
                pass
        # Wait up to 3 seconds
        try:
            psutil.wait_procs(targets, timeout=3)
        except Exception:
            pass
        # Force kill remaining
        for p in targets:
            try:
                if psutil.pid_exists(p.pid):
                    p.kill()
                stopped_pids.append(p.pid)
            except Exception:
                pass
        
        # Also kill any Chromium/Playwright processes tied to the WhatsApp profile
        try:
            profile_kills = _kill_browser_profile_processes()
            stopped_pids.extend(profile_kills)
        except Exception:
            pass

    # Avoid killing all Python processes; we already terminated targeted ones above
        
        if stopped_pids:
            return {"success": True, "stopped_pids": stopped_pids, "message": f"Stopped {len(stopped_pids)} processes"}
        else:
            return {"success": True, "message": "No WhatsApp automator process found (may already be stopped)"}
    except Exception as e:
        return {"success": False, "error": str(e)}

class FileContent(BaseModel):
    content: str

@app.get('/api/files/{filename}')
def api_get_file(filename: str):
    """Get content of a file (docs, perfil, ultimo_contexto, etc.)"""
    try:
        # Security: only allow specific files
        allowed_files = {
            "ejemplo_chat": "Docs/ejemplo_chat.txt",
            "perfil": "Docs/Perfil.txt", 
            "ultimo_contexto": "Docs/Ultimo_contexto.txt"
        }
        
        if filename not in allowed_files:
            raise HTTPException(status_code=404, detail="File not found")
        
        file_path = os.path.join(os.path.dirname(__file__), allowed_files[filename])
        
        if not os.path.exists(file_path):
            # Create file if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("")
        
        # Try different encodings
        content = ""
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
        
        return {"filename": filename, "content": content, "path": file_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put('/api/files/{filename}')
def api_update_file(filename: str, file_content: FileContent):
    """Update content of a file"""
    try:
        allowed_files = {
            "ejemplo_chat": "Docs/ejemplo_chat.txt",
            "perfil": "Docs/Perfil.txt", 
            "ultimo_contexto": "Docs/Ultimo_contexto.txt"
        }
        
        if filename not in allowed_files:
            raise HTTPException(status_code=404, detail="File not found")
        
        file_path = os.path.join(os.path.dirname(__file__), allowed_files[filename])
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Write content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_content.content)
        
        return {"success": True, "filename": filename, "message": "File updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/chats')
def api_get_chats():
    """Get list of chat contexts"""
    try:
        contextos_dir = os.path.join(os.path.dirname(__file__), "contextos")
        if not os.path.exists(contextos_dir):
            os.makedirs(contextos_dir, exist_ok=True)

        chats = []
        for name in os.listdir(contextos_dir):
            path = os.path.join(contextos_dir, name)
            if os.path.isdir(path) and name.startswith('chat_'):
                chats.append(name[len('chat_'):])

        return {"chats": sorted(chats)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/chats/{chat_id}')
def api_get_chat_context(chat_id: str):
    """Get context for a specific chat"""
    try:
        # Sanitize chat_id and prepare result structure
        chat_id = "".join(c for c in chat_id if c.isalnum() or c in "_-")
        chat_dir = os.path.join(os.path.dirname(__file__), "contextos", f"chat_{chat_id}")
        os.makedirs(chat_dir, exist_ok=True)

        result = {"chat_id": chat_id, "files": {"perfil": "", "contexto": "", "objetivo": "", "historial": []}, "automator_pid": None, "browser_pids": []}

        # Read perfil, contexto, objetivo if present
        perfil_path = os.path.join(chat_dir, "perfil.txt")
        contexto_path = os.path.join(chat_dir, "contexto.txt")
        objetivo_path = os.path.join(chat_dir, "objetivo.txt")
        if os.path.exists(perfil_path):
            try:
                with open(perfil_path, 'r', encoding='utf-8') as f:
                    result["files"]["perfil"] = f.read()
            except Exception:
                result["files"]["perfil"] = ""
        if os.path.exists(contexto_path):
            try:
                with open(contexto_path, 'r', encoding='utf-8') as f:
                    result["files"]["contexto"] = f.read()
            except Exception:
                result["files"]["contexto"] = ""
        if os.path.exists(objetivo_path):
            try:
                with open(objetivo_path, 'r', encoding='utf-8') as f:
                    result["files"]["objetivo"] = f.read()
            except Exception:
                result["files"]["objetivo"] = ""

        # Detect running automator by matching its script in process cmdlines
        if psutil is not None:
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if _script_match_in_cmdline(proc, 'whatsapp_automator.py'):
                            result["automator_pid"] = proc.info.get('pid')
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception:
                pass

        # Detect browser processes attached to the playwright profile
        try:
            profile = _get_playwright_profile_dir()
            prof_norm = profile.lower().replace('\\', '/').strip() if profile else ''
            if prof_norm and psutil is not None:
                targets = ['chrome.exe', 'msedge.exe', 'chromium.exe', 'chrome', 'msedge', 'chromium']
                for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        name = (p.info.get('name') or '').lower()
                        cmd = ' '.join(p.info.get('cmdline') or []).lower().replace('\\', '/')
                        if any(t in name for t in targets) and prof_norm in cmd:
                            result["browser_pids"].append(p.info.get('pid'))
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
        except Exception:
            pass

        # Load historial if available
        historial_path = os.path.join(chat_dir, 'historial.json')
        try:
            if os.path.exists(historial_path):
                with open(historial_path, 'r', encoding='utf-8') as f:
                    result["files"]["historial"] = json.load(f)
        except Exception:
            result["files"]["historial"] = []

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ChatContextUpdate(BaseModel):
    perfil: Optional[str] = None
    contexto: Optional[str] = None
    objetivo: Optional[str] = None

@app.put('/api/chats/{chat_id}')
def api_update_chat_context(chat_id: str, update: ChatContextUpdate):
    """Update context for a specific chat"""
    try:
        # Sanitize chat_id
        chat_id = "".join(c for c in chat_id if c.isalnum() or c in "_-")
        
        chat_dir = os.path.join(os.path.dirname(__file__), "contextos", f"chat_{chat_id}")
        os.makedirs(chat_dir, exist_ok=True)
        
        updated_files = []
        
        if update.perfil is not None:
            perfil_path = os.path.join(chat_dir, "perfil.txt")
            with open(perfil_path, 'w', encoding='utf-8') as f:
                f.write(update.perfil)
            updated_files.append("perfil.txt")
        
        if update.contexto is not None:
            contexto_path = os.path.join(chat_dir, "contexto.txt") 
            with open(contexto_path, 'w', encoding='utf-8') as f:
                f.write(update.contexto)
            updated_files.append("contexto.txt")
        if update.objetivo is not None:
            objetivo_path = os.path.join(chat_dir, "objetivo.txt")
            with open(objetivo_path, 'w', encoding='utf-8') as f:
                f.write(update.objetivo)
            updated_files.append("objetivo.txt")

        # Best-effort sync to DB ChatProfile
        try:
            session = get_session()
            profile = session.query(ChatProfile).filter(ChatProfile.chat_id == chat_id).first()
            if not profile:
                profile = ChatProfile()
                setattr(profile, 'chat_id', chat_id)
                session.add(profile)
            if update.contexto is not None:
                setattr(profile, 'initial_context', update.contexto)
            if update.objetivo is not None:
                setattr(profile, 'objective', update.objetivo)
            session.commit()
            session.close()
        except Exception:
            pass
        
        return {"success": True, "chat_id": chat_id, "updated_files": updated_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/chats/{chat_id}/refresh-context')
def api_refresh_chat_context(chat_id: str, user=Depends(verify_token)):
    """Execute the reasoner to update perfil/contexto files and activate a new strategy for this chat."""
    try:
        # Sanitize chat_id
        chat_id = "".join(c for c in chat_id if c.isalnum() or c in "_-")
        result = update_chat_context_and_profile(chat_id)
        return {"success": True, "chat_id": chat_id, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/status')
def api_status():
    # lightweight status payload consumed by the web UI
    # Merge settings files to get current state
    sfile = os.path.join(os.path.dirname(__file__), 'data', 'settings.json')
    pfile = os.path.join(os.path.dirname(__file__), 'data', 'prompts.json')
    
    settings = {'temperature': 0.7, 'max_tokens': 512, 'reason_after_messages': 10, 'chat_enabled': True}
    if os.path.exists(sfile):
        try:
            import json
            with open(sfile,'r',encoding='utf-8') as f:
                settings.update(json.load(f))
        except Exception:
            pass
    
    prompts = {'conversational': 'Responde de forma útil y breve.', 'reasoner': 'Piensa paso a paso antes de responder.', 'conversation': ''}
    if os.path.exists(pfile):
        try:
            import json
            with open(pfile,'r',encoding='utf-8') as f:
                prompts.update(json.load(f))
        except Exception:
            pass
    
    return {
        'status': 'ok',
        'app': 'admin-panel',
        'chat_enabled': settings.get('chat_enabled', True),
        'settings': {
            'temperature': settings.get('temperature', 0.7),
            'max_tokens': settings.get('max_tokens', 512),
            'reason_after_messages': settings.get('reason_after_messages', 10)
        },
        'prompts': prompts
    }


class PromptsIn(BaseModel):
    conversational: Optional[str] = None
    reasoner: Optional[str] = None
    conversation: Optional[str] = None


@app.put('/api/prompts')
def api_update_prompts(payload: PromptsIn, user=Depends(verify_token)):
    # TODO: persist to DB — for now store in memory or simple file
    pfile = os.path.join(os.path.dirname(__file__), 'data', 'prompts.json')
    data = {}
    if os.path.exists(pfile):
        try:
            import json
            with open(pfile,'r',encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}
    if payload.conversational is not None:
        data['conversational'] = payload.conversational
    if payload.reasoner is not None:
        data['reasoner'] = payload.reasoner
    if payload.conversation is not None:
        data['conversation'] = payload.conversation
    os.makedirs(os.path.dirname(pfile), exist_ok=True)
    with open(pfile,'w',encoding='utf-8') as f:
        import json
        json.dump(data,f,ensure_ascii=False,indent=2)
    return {'ok': True}


@app.get('/api/prompts')
def api_get_prompts():
    pfile = os.path.join(os.path.dirname(__file__), 'data', 'prompts.json')
    if os.path.exists(pfile):
        import json
        with open(pfile,'r',encoding='utf-8') as f:
            return json.load(f)
    return {'conversational': '', 'reasoner': '', 'conversation': ''}


class SettingsIn(BaseModel):
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    reason_after_messages: Optional[int] = None
    respond_to_all: Optional[bool] = None  # New setting


@app.put('/api/settings')
def api_update_settings(payload: SettingsIn, user=Depends(verify_token)):
    sfile = os.path.join(os.path.dirname(__file__), 'data', 'settings.json')
    settings = {}
    if os.path.exists(sfile):
        try:
            import json
            with open(sfile,'r',encoding='utf-8') as f:
                settings = json.load(f)
        except Exception:
            settings = {}
    if payload.temperature is not None:
        settings['temperature'] = payload.temperature
    if payload.max_tokens is not None:
        settings['max_tokens'] = payload.max_tokens
    if payload.reason_after_messages is not None:
        settings['reason_after_messages'] = payload.reason_after_messages
    if payload.respond_to_all is not None:
        settings['respond_to_all'] = payload.respond_to_all
    os.makedirs(os.path.dirname(sfile), exist_ok=True)
    import json
    with open(sfile,'w',encoding='utf-8') as f:
        json.dump(settings,f,ensure_ascii=False,indent=2)
    return {'ok': True}


@app.get('/api/settings')
def api_get_settings():
    sfile = os.path.join(os.path.dirname(__file__), 'data', 'settings.json')
    if os.path.exists(sfile):
        import json
        with open(sfile,'r',encoding='utf-8') as f:
            return json.load(f)
    return {'temperature': 0.7, 'max_tokens': 512, 'reason_after_messages': 10, 'respond_to_all': False}


class ContactCreate(BaseModel):
    contact_id: str
    label: Optional[str] = None


class AllowedContactCreate(BaseModel):
    chat_id: str
    initial_context: Optional[str] = ""
    objective: Optional[str] = ""
    perfil: Optional[str] = ""


@app.post('/api/contacts')
def api_create_contact(payload: ContactCreate, user=Depends(verify_token)):
    session = get_session()
    try:
        from crypto import encrypt_text
        enc = encrypt_text(payload.contact_id)
        c = AllowedContact(contact_id=enc, label=payload.label, owner_user=user)
        session.add(c)
        session.commit()
        session.refresh(c)
        return {'id': c.id, 'label': c.label}
    finally:
        session.close()


@app.get('/api/contacts')
def api_list_contacts(user=Depends(verify_token)):
    session = get_session()
    items = session.query(AllowedContact).order_by(AllowedContact.added_at.desc()).limit(200).all()
    session.close()
    return [{'id': i.id, 'label': i.label} for i in items]


@app.get('/api/analytics')
def api_analytics(user=Depends(verify_token)):
    # lightweight analytics based on counts in DB
    session = get_session()
    total_models = session.query(ModelConfig).count()
    total_contacts = session.query(AllowedContact).count()
    total_daily = session.query(DailyContext).count()
    session.close()
    return {'models': total_models, 'contacts': total_contacts, 'daily_contexts': total_daily}


# New endpoints for enhanced contact management
@app.post('/api/allowed-contacts')
def api_create_allowed_contact(payload: AllowedContactCreate, user=Depends(verify_token)):
    """Create a new allowed contact with context and objective"""
    session = get_session()
    try:
        # Create or update contact
        contact = session.query(Contact).filter(Contact.chat_id == payload.chat_id).first()
        if not contact:
            contact = Contact(chat_id=payload.chat_id, auto_enabled=True)
            session.add(contact)
        
        # Create or update chat profile
        profile = session.query(ChatProfile).filter(ChatProfile.chat_id == payload.chat_id).first()
        if not profile:
            profile = ChatProfile()
            setattr(profile, 'chat_id', payload.chat_id)
            setattr(profile, 'initial_context', payload.initial_context)
            setattr(profile, 'objective', payload.objective)
            setattr(profile, 'is_ready', True)
            session.add(profile)
        else:
            setattr(profile, 'initial_context', payload.initial_context)
            setattr(profile, 'objective', payload.objective)
            setattr(profile, 'is_ready', True)
        
        session.commit()

        # Persist filesystem files under contextos/chat_{chat_id}
        try:
            chat_dir = os.path.join(os.path.dirname(__file__), "contextos", f"chat_{payload.chat_id}")
            os.makedirs(chat_dir, exist_ok=True)
            if (payload.perfil or "").strip():
                with open(os.path.join(chat_dir, 'perfil.txt'), 'w', encoding='utf-8') as f:
                    f.write(payload.perfil or "")
            if (payload.initial_context or "").strip():
                with open(os.path.join(chat_dir, 'contexto.txt'), 'w', encoding='utf-8') as f:
                    f.write(payload.initial_context or "")
            if (payload.objective or "").strip():
                with open(os.path.join(chat_dir, 'objetivo.txt'), 'w', encoding='utf-8') as f:
                    f.write(payload.objective or "")
        except Exception:
            pass
        return {
            'success': True,
            'chat_id': payload.chat_id,
            'message': f'Contact {payload.chat_id} added successfully'
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get('/api/allowed-contacts')
def api_list_allowed_contacts(user=Depends(verify_token)):
    """List all allowed contacts with their context and objectives"""
    session = get_session()
    try:
        # Join contacts with their profiles
        results = session.query(Contact, ChatProfile).outerjoin(
            ChatProfile, Contact.chat_id == ChatProfile.chat_id
        ).filter(Contact.auto_enabled).all()
        
        contacts = []
        for contact, profile in results:
            contacts.append({
                'chat_id': contact.chat_id,
                'name': contact.name or contact.chat_id,
                'initial_context': profile.initial_context if profile else "",
                'objective': profile.objective if profile else "",
                'perfil': True if os.path.exists(os.path.join(os.path.dirname(__file__), 'contextos', f"chat_{contact.chat_id}", 'perfil.txt')) else False,
                'is_ready': profile.is_ready if profile else False,
                'created_at': contact.created_at.isoformat() if contact.created_at else None
            })
        
        return contacts
    finally:
        session.close()


@app.delete('/api/allowed-contacts/{chat_id}')
def api_remove_allowed_contact(chat_id: str, user=Depends(verify_token)):
    """Remove an allowed contact"""
    session = get_session()
    try:
        # Remove contact
        contact = session.query(Contact).filter(Contact.chat_id == chat_id).first()
        if contact:
            session.delete(contact)
        
        # Remove profile
        profile = session.query(ChatProfile).filter(ChatProfile.chat_id == chat_id).first()
        if profile:
            session.delete(profile)
        
        # Remove counters
        counter = session.query(ChatCounter).filter(ChatCounter.chat_id == chat_id).first()
        if counter:
            session.delete(counter)
        
        session.commit()
        return {
            'success': True,
            'message': f'Contact {chat_id} removed successfully'
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.post('/api/auth/login', response_model=Dict[str, Any])
async def api_login(request: Request, credentials: Dict[str, str]):
    """Login con JWT y auditoría"""
    username = credentials.get("username")
    password = credentials.get("password")
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Usuario y password requeridos")
    
    # Obtener IP del cliente
    client_ip = request.client.host if request.client else None
    
    auth_result = auth_manager.authenticate_user(username, password)
    if not auth_result:
        # Log de intento fallido
        log_login(username, "unknown", ip=client_ip, success=False, error="Credenciales inválidas")
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
        
    access_token = auth_manager.create_access_token(auth_result)
    
    # Log de login exitoso
    log_login(username, auth_result.get("role", "unknown"), ip=client_ip, success=True)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_info": auth_result,
        "expires_in": auth_manager.access_token_expire_minutes * 60
    }

@app.post('/api/auth/logout')
async def api_logout(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Logout con auditoría"""
    client_ip = request.client.host if request.client else None
    log_logout(
        current_user.get("username", "unknown"),
        current_user.get("role", "unknown"),
        ip=client_ip
    )
    return {"message": "Logout exitoso"}

@app.get('/api/auth/me', dependencies=[Depends(security)])
async def api_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Obtener info del usuario actual"""
    return current_user


@app.post('/api/settings/chat/toggle')
def api_toggle_chat(user=Depends(verify_token)):
    # flip a boolean in settings
    sfile = os.path.join(os.path.dirname(__file__), 'data', 'settings.json')
    settings = {}
    if os.path.exists(sfile):
        import json
        with open(sfile,'r',encoding='utf-8') as f:
            settings = json.load(f)
    current = settings.get('chat_enabled', True)
    settings['chat_enabled'] = not current
    import json
    os.makedirs(os.path.dirname(sfile), exist_ok=True)
    with open(sfile,'w',encoding='utf-8') as f:
        json.dump(settings,f,ensure_ascii=False,indent=2)
    return {'chat_enabled': settings['chat_enabled']}


class ScheduleIn(BaseModel):
    chat_id: str
    message: str
    when: Optional[str] = None  # ISO timestamp or 'now'


@app.post('/api/schedule')
def api_schedule(payload: ScheduleIn, user=Depends(verify_token)):
    sfile = os.path.join(os.path.dirname(__file__), 'data', 'scheduled.json')
    os.makedirs(os.path.dirname(sfile), exist_ok=True)
    schedules = []
    if os.path.exists(sfile):
        import json
        try:
            with open(sfile,'r',encoding='utf-8') as f:
                schedules = json.load(f)
        except Exception:
            schedules = []
    entry = {'chat_id': payload.chat_id, 'message': payload.message, 'when': payload.when or 'now'}
    schedules.append(entry)
    import json
    with open(sfile,'w',encoding='utf-8') as f:
        json.dump(schedules,f,ensure_ascii=False,indent=2)
    return {'ok': True}


def event_stream():
    import time
    import json
    sfile = os.path.join(os.path.dirname(__file__), 'data', 'status.json')
    while True:
        payload = {'time': time.time()}
        if os.path.exists(sfile):
            try:
                with open(sfile,'r',encoding='utf-8') as f:
                    payload.update(json.load(f))
            except Exception:
                pass
        yield f"data: {json.dumps(payload)}\n\n"
        time.sleep(1)


@app.get('/api/events')
def api_events():
    return StreamingResponse(event_stream(), media_type='text/event-stream')


# ============== MEMORY / CONVERSATION RESET API ==============
class ClearChatIn(BaseModel):
    chat_id: str


@app.post('/api/conversations/clear', response_class=JSONResponse)
def api_clear_conversation(payload: ClearChatIn, user=Depends(verify_token)):
    try:
        n = chat_sessions.clear_conversation_history(payload.chat_id)
        return {"success": True, "deleted": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/conversations/clear-all', response_class=JSONResponse)
def api_clear_all_conversations(user=Depends(verify_token)):
    try:
        n = chat_sessions.clear_all_conversation_histories()
        return {"success": True, "deleted": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ChatIn(BaseModel):
        chat_id: str
        message: str


@app.post('/api/chat')
def api_chat(payload: ChatIn):
        try:
                history = chat_sessions.load_last_context(payload.chat_id) or []
                # call stub chat
                reply = stub_chat.chat(payload.message, payload.chat_id, history)
                # append and save
                history.append({'role':'user','content':payload.message})
                history.append({'role':'assistant','content':reply})
                chat_sessions.save_context(payload.chat_id, history)
                return JSONResponse({'reply': reply})
        except Exception as e:
                return JSONResponse({'error': str(e)}, status_code=500)


@app.post('/api/automator/test-reply')
def api_test_reply():
    """Test endpoint to verify LM Studio connection and reply generation"""
    try:
        test_message = "Hola, esto es una prueba"
        test_chat_id = "test_chat"
        test_history = []
        
        # Test stub_chat directly
        reply = stub_chat.chat(test_message, test_chat_id, test_history)
        
        return {
            "success": True,
            "test_message": test_message,
            "reply": reply,
            "message": "LM Studio connection and reply generation working"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Error testing reply generation"
        }


# ============== MANUAL MESSAGE COMPOSITION API ==============

class MessageComposeRequest(BaseModel):
    chat_id: str
    objective: str
    additional_context: Optional[str] = ""

class MessageSendRequest(BaseModel):
    chat_id: str
    message: str
    media: Optional[dict] = None  # {"fileId": str, "type": str}

class BulkMessageRequest(BaseModel):
    contacts: List[str]  # List of contact numbers
    template: str
    objective: str
    media: Optional[dict] = None  # {"fileId": str, "type": str}

@app.post('/api/chat/compose')
def api_compose_message(payload: MessageComposeRequest):
    """Generate a message using AI for a specific contact and objective"""
    try:
        # Create a specialized prompt for message composition
        compose_prompt = f"""Eres un asistente experto en comunicación. Tu tarea es generar un mensaje de WhatsApp profesional y personalizado.

OBJETIVO DEL MENSAJE: {payload.objective}

INFORMACIÓN ADICIONAL: {payload.additional_context if payload.additional_context else "Ninguna"}

INSTRUCCIONES:
1. Genera un mensaje claro, conciso y profesional
2. Adapta el tono según el objetivo (formal para citas médicas, amigable para recordatorios personales)
3. Incluye solo el texto del mensaje, sin explicaciones adicionales
4. Máximo 200 palabras
5. Evita usar emojis excesivos
6. Sé directo y específico

Genera ÚNICAMENTE el texto del mensaje:"""

        # Call stub_chat to generate the message
        generated_message = stub_chat.chat(compose_prompt, payload.chat_id, [])
        
        if generated_message:
            return {"success": True, "reply": generated_message}
        else:
            return {"success": False, "error": "No se pudo generar el mensaje. Verifica que LM Studio esté funcionando."}
    
    except Exception as e:
        return {"success": False, "error": f"Error generando mensaje: {str(e)}"}

@app.post('/api/whatsapp/send')
def api_send_whatsapp_message(payload: MessageSendRequest):
    """Send a message through WhatsApp (requires WhatsApp automation to be running)"""
    try:
        # Check if WhatsApp automator is running
        status = api_whatsapp_status()
        if status.get("status") != "running":
            return {"success": False, "error": "WhatsApp automator no está ejecutándose"}
        
        # Queue the message for the WhatsApp automator to send
        try:
            import json
            import os
            import logging
            from datetime import datetime
            
            # Create manual messages queue file if it doesn't exist
            here = os.path.dirname(__file__)
            queue_file = os.path.join(here, 'data', 'manual_queue.json')
            
            # Load existing queue
            try:
                with open(queue_file, 'r', encoding='utf-8') as f:
                    queue = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                queue = []
            
            # Add new message to queue
            message_entry = {
                'id': f"manual_{int(datetime.now().timestamp())}",
                'chat_id': payload.chat_id,
                'message': payload.message,
                'timestamp': datetime.now().isoformat(),
                'status': 'pending'
            }
            
            if payload.media:
                message_entry['media'] = json.dumps(payload.media)
            
            queue.append(message_entry)
            
            # Save updated queue
            with open(queue_file, 'w', encoding='utf-8') as f:
                json.dump(queue, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Queued manual message to {payload.chat_id}: {payload.message}")
            
        except Exception as e:
            import logging
            logging.error(f"Error queuing manual message: {e}")
            return {"success": False, "error": f"Error al programar mensaje: {str(e)}"}
        
        # Store the message in chat history
        try:
            history = chat_sessions.load_last_context(payload.chat_id) or []
            message_entry = {
                'role': 'assistant', 
                'content': payload.message, 
                'manual': True
            }
            if payload.media:
                message_entry['media'] = json.dumps(payload.media)
            
            history.append(message_entry)
            chat_sessions.save_context(payload.chat_id, history)
        except Exception as e:
            print(f"Error saving manual message to history: {e}")
        
        media_text = " con archivo multimedia" if payload.media else ""
        return {
            "success": True,
            "message": f"Mensaje{media_text} enviado a cola para {payload.chat_id}",
            "note": "El mensaje ha sido programado y será enviado por el automator de WhatsApp."
        }
    
    except Exception as e:
        return {"success": False, "error": f"Error enviando mensaje: {str(e)}"}

@app.post('/api/whatsapp/bulk-send')
async def api_bulk_send_messages(payload: BulkMessageRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Send bulk messages to multiple contacts usando el sistema de cola"""
    try:
        # Crear campaña
        campaign_id = queue_manager.create_campaign(
            name=f"Bulk {payload.objective[:50]}",
            created_by=current_user.get("username", "unknown"),
            total_messages=len(payload.contacts),
            metadata={
                "objective": payload.objective,
                "template": payload.template
            }
        )
        
        results = []
        
        for contact_number in payload.contacts:
            try:
                # Generate personalized content for this contact
                compose_prompt = f"""Eres un asistente experto en comunicación. Genera contenido personalizado basado en el objetivo.

OBJETIVO: {payload.objective}
CONTACTO: {contact_number}

INSTRUCCIONES:
1. Genera contenido específico y personalizado
2. Mantén un tono profesional y amigable
3. Sé conciso y directo
4. Máximo 150 palabras
5. Solo proporciona el contenido, sin explicaciones adicionales

Genera el contenido personalizado:"""

                # Generate personalized content
                personalized_content = stub_chat.chat(compose_prompt, contact_number, [])
                
                if personalized_content:
                    # Replace template variables
                    final_message = payload.template.replace('{custom}', personalized_content)
                else:
                    # Fallback without personalization
                    final_message = payload.template.replace('{custom}', 'contenido personalizado')
                
                # Encolar mensaje en lugar de enviar directo
                message_id = queue_manager.enqueue_message(
                    chat_id=contact_number,
                    message=final_message,
                    priority=0,
                    metadata={
                        "campaign_id": campaign_id,
                        "bulk": True,
                        "objective": payload.objective
                    }
                )
                
                # Store in chat history
                try:
                    history = chat_sessions.load_last_context(contact_number) or []
                    history.append({'role': 'assistant', 'content': final_message, 'bulk': True, 'campaign_id': campaign_id})
                    chat_sessions.save_context(contact_number, history)
                except Exception as e:
                    print(f"Error saving bulk message to history for {contact_number}: {e}")
                
                results.append({
                    "contact": contact_number,
                    "success": True,
                    "message_id": message_id,
                    "message": final_message
                })
                
            except Exception as e:
                results.append({
                    "contact": contact_number,
                    "success": False,
                    "error": f"Error procesando mensaje para {contact_number}: {str(e)}"
                })
        
        successful_sends = sum(1 for r in results if r["success"])
        total_contacts = len(payload.contacts)
        
        # Log de auditoría
        log_bulk_send(
            current_user.get("username", "unknown"),
            current_user.get("role", "unknown"),
            campaign_id,
            total_contacts,
            {"objective": payload.objective, "successful": successful_sends}
        )
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "total": total_contacts,
            "successful": successful_sends,
            "failed": total_contacts - successful_sends,
            "results": results,
            "message": f"Campaña creada. {successful_sends}/{total_contacts} mensajes encolados correctamente."
        }
        
    except Exception as e:
        return {"success": False, "error": f"Error en bulk send: {str(e)}"}

@app.post('/api/media/upload')
async def upload_media_file(file: UploadFile = File(...), messageType: str = "manual"):
    """Upload media file for message attachments"""
    try:
        # Validate file type
        allowed_types = [
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'video/mp4', 'video/avi', 'video/mov',
            'application/pdf', 'application/msword', 
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ]
        
        if file.content_type not in allowed_types:
            return {"success": False, "error": f"Tipo de archivo no permitido: {file.content_type}"}
        
        # Validate file size (max 25MB)
        max_size = 25 * 1024 * 1024  # 25MB
        contents = await file.read()
        if len(contents) > max_size:
            return {"success": False, "error": "Archivo muy grande. Máximo 25MB permitido"}
        
        # Create media directory if it doesn't exist
        import os
        media_dir = "media_uploads"
        if not os.path.exists(media_dir):
            os.makedirs(media_dir)
        
        # Generate unique filename
        import uuid
        from datetime import datetime
        filename = file.filename or "uploaded_file"
        file_extension = os.path.splitext(filename)[1]
        unique_filename = f"{messageType}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{file_extension}"
        file_path = os.path.join(media_dir, unique_filename)
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Store file info (in production, you'd store this in database)
        file_info = {
            "fileId": unique_filename,
            "originalName": filename,
            "contentType": file.content_type,
            "size": len(contents),
            "path": file_path,
            "messageType": messageType,
            "uploadTime": datetime.now().isoformat()
        }
        
        # Log upload for debugging
        import logging
        logging.info(f"Media file uploaded: {file_info}")
        
        return {
            "success": True,
            "fileId": unique_filename,
            "originalName": filename,
            "size": len(contents)
        }
        
    except Exception as e:
        return {"success": False, "error": f"Error subiendo archivo: {str(e)}"}


# ============== DAILY CONTEXTS API ==============
class DailyContextCreate(BaseModel):
    text: str
    active: Optional[bool] = True

@app.post('/api/daily-contexts')
def api_create_daily_context(payload: DailyContextCreate, user=Depends(verify_token)):
    """Create a new daily context"""
    session = get_session()
    try:
        context = DailyContext(
            text=payload.text,
            active=payload.active
        )
        
        session.add(context)
        session.commit()
        
        return {
            "id": context.id,
            "text": context.text,
            "active": context.active,
            "created_at": context.created_at.isoformat() if context.created_at else None
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get('/api/daily-contexts')
def api_list_daily_contexts(user=Depends(verify_token)):
    """List all daily contexts"""
    session = get_session()
    try:
        contexts = session.query(DailyContext).all()
        return [
            {
                "id": ctx.id,
                "text": ctx.text,
                "active": ctx.active,
                "created_at": ctx.created_at.isoformat() if ctx.created_at else None
            }
            for ctx in contexts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ============== USER CONTEXTS API ==============
class UserContextCreate(BaseModel):
    user_id: str
    text: str
    source: Optional[str] = "manual_admin"

@app.post('/api/user-contexts')
def api_create_user_context(payload: UserContextCreate, user=Depends(verify_token)):
    """Create a new user context"""
    session = get_session()
    try:
        context = UserContext(
            user_id=payload.user_id,
            text=payload.text,
            source=payload.source
        )
        
        session.add(context)
        session.commit()
        
        return {
            "id": context.id,
            "user_id": context.user_id,
            "text": context.text,
            "source": context.source,
            "created_at": context.created_at.isoformat() if getattr(context, 'created_at') else None
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get('/api/user-contexts')
def api_list_user_contexts(user_id: Optional[str] = None, user=Depends(verify_token)):
    """List user contexts, optionally filtered by user_id"""
    session = get_session()
    try:
        query = session.query(UserContext)
        if user_id:
            query = query.filter(UserContext.user_id == user_id)
        
        contexts = query.all()
        return [
            {
                "id": ctx.id,
                "user_id": ctx.user_id,
                "text": ctx.text,
                "source": ctx.source,
                "created_at": ctx.created_at.isoformat() if getattr(ctx, 'created_at') else None
            }
            for ctx in contexts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ==================== Online Models API Endpoints ====================

@app.get('/api/models/local')
def api_list_local_models(user=Depends(verify_token)):
    """List only local models (LM Studio models)"""
    session = get_session()
    try:
        models = session.query(ModelConfig).filter(ModelConfig.model_type == 'local').all()
        return [
            {
                "id": m.id,
                "name": m.name,
                "provider": m.provider,
                "model_type": m.model_type,
                "active": m.active
            }
            for m in models
        ]
    finally:
        session.close()


@app.get('/api/models/online')
def api_list_online_models(user=Depends(verify_token)):
    """List only online models (API-based models)"""
    session = get_session()
    try:
        models = session.query(ModelConfig).filter(ModelConfig.model_type == 'online').all()
        return [
            {
                "id": m.id,
                "name": m.name,
                "provider": m.provider,
                "model_type": m.model_type,
                "active": m.active,
                "config": m.config
            }
            for m in models
        ]
    finally:
        session.close()


@app.get('/api/models/online/available')
def api_available_online_models():
    """Get available online models by provider"""
    return {
        "google": {
            "provider": "google",
            "models": [
                {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "description": "Google's most capable model"},
                {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "description": "Fast and efficient model"},
                {"id": "gemini-pro", "name": "Gemini Pro", "description": "Google's general purpose model"},
            ]
        },
        "openai": {
            "provider": "openai", 
            "models": [
                {"id": "gpt-4o", "name": "GPT-4o", "description": "OpenAI's most advanced model"},
                {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "description": "Faster, cost-effective model"},
                {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "description": "Latest GPT-4 with improved capabilities"},
                {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "description": "Fast and cost-effective model"},
            ]
        },
        "anthropic": {
            "provider": "anthropic",
            "models": [
                {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "description": "Anthropic's most capable model"},
                {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "description": "Most powerful Claude model"},
                {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet", "description": "Balanced performance and speed"},
                {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku", "description": "Fast and cost-effective"},
            ]
        },
        "x-ai": {
            "provider": "x-ai",
            "models": [
                {"id": "grok-beta", "name": "Grok Beta", "description": "X's conversational AI model"},
                {"id": "grok-vision-beta", "name": "Grok Vision Beta", "description": "Grok with image understanding"},
            ]
        }
    }


class OnlineModelConfig(BaseModel):
    name: str
    provider: str  # "google", "openai", "anthropic", "x-ai"
    model_id: str  # The actual model ID from the provider
    api_key: str
    base_url: Optional[str] = None
    active: bool = True


@app.post('/api/models/online')
def api_create_online_model(config: OnlineModelConfig, user=Depends(verify_token)):
    """Create a new online model configuration"""
    session = get_session()
    try:
        # Encrypt the API key
        from crypto import encrypt_text
        encrypted_key = encrypt_text(config.api_key)
        
        model_config = {
            "model_id": config.model_id,
            "api_key_encrypted": encrypted_key,
            "base_url": config.base_url
        }
        
        model = ModelConfig(
            name=config.name,
            provider=config.provider,
            model_type='online',
            config=model_config,
            active=config.active
        )
        
        session.add(model)
        session.commit()
        session.refresh(model)
        
        return {
            "id": model.id,
            "name": model.name,
            "provider": model.provider,
            "model_type": model.model_type,
            "active": model.active
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.put('/api/models/online/{model_id}')
def api_update_online_model(model_id: int, config: OnlineModelConfig, user=Depends(verify_token)):
    """Update an online model configuration"""
    session = get_session()
    try:
        model = session.query(ModelConfig).filter(ModelConfig.id == model_id, ModelConfig.model_type == 'online').first()
        if not model:
            raise HTTPException(status_code=404, detail="Online model not found")
        
        # Encrypt the new API key
        from crypto import encrypt_text
        encrypted_key = encrypt_text(config.api_key)
        
        model_config = {
            "model_id": config.model_id,
            "api_key_encrypted": encrypted_key,
            "base_url": config.base_url
        }
        
        setattr(model, 'name', config.name)
        setattr(model, 'provider', config.provider)
        setattr(model, 'config', model_config)
        setattr(model, 'active', config.active)
        
        session.commit()
        
        return {
            "id": model.id,
            "name": model.name,
            "provider": model.provider,
            "model_type": model.model_type,
            "active": model.active
        }
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.delete('/api/models/online/{model_id}')
def api_delete_online_model(model_id: int, user=Depends(verify_token)):
    """Delete an online model configuration"""
    session = get_session()
    try:
        model = session.query(ModelConfig).filter(ModelConfig.id == model_id, ModelConfig.model_type == 'online').first()
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


# ==================== Enhanced LM Studio API (Local Models Only) ====================

@app.get('/api/lmstudio/models/local-only')
def api_lmstudio_local_models():
    """NUEVA FUNCIÓN FILTRADA - Solo modelos permitidos por Pablo según especificaciones"""
    
    try:
        # Usar nuestra nueva función filtrada
        result = api_lmstudio_models()
        
        # Si hay error, devolver estructura compatible con frontend
        if result.get('status') == 'error':
            return {
                'status': 'error',
                'models': [],
                'local_models': [],
                'lm_studio_running': False,
                'error': result.get('error', 'Error desconocido'),
                'note': 'No se detectó LM Studio ni modelos locales. Inicia LM Studio en 127.0.0.1:1234 o contacta soporte.'
            }
        
        # Convertir nueva estructura a estructura esperada por frontend
        main_models = result.get('main_models', [])
        reasoning_models = result.get('reasoning_models', [])
        
        # Combinar modelos principales y razonadores para compatibilidad con frontend
        all_filtered = main_models + reasoning_models
        
        # Estructura compatible con el frontend existente pero con modelos filtrados
        return {
            'status': 'success',
            'lm_studio_running': result.get('lm_studio_running', False),
            'models': main_models,  # SOLO MODELOS PRINCIPALES para selector principal
            'reasoning_models': reasoning_models,  # NUEVOS: SOLO RAZONADORES para selector de razonamiento
            'local_models': [],  # Vacío - no necesitamos fallback porque LM Studio debe estar activo
            'port': result.get('port', 1234),
            'current_model': result.get('current_model', 'ninguno'),
            'main_models_count': len(main_models),
            'reasoning_models_count': len(reasoning_models),
            'note': f"Mostrando {len(all_filtered)} modelos permitidos: {len(main_models)} principales + {len(reasoning_models)} razonadores" if all_filtered else "No hay modelos permitidos cargados. Inicia LM Studio y carga un modelo de la lista permitida."
        }
        
    except Exception as e:
        # Error handling robusto
        import traceback
        error_msg = f"Error en filtro de modelos: {str(e)}"
        print(f"ERROR: {error_msg}")
        print(f"TRACEBACK: {traceback.format_exc()}")
        
        return {
            'status': 'error',
            'models': [],
            'local_models': [],
            'lm_studio_running': False,
            'error': error_msg,
            'note': 'Error interno en el filtro de modelos. Revisa logs.'
        }


# ==================== Model Type Migration ====================

@app.post('/api/admin/migrate-model-types')
def api_migrate_model_types(user=Depends(verify_token)):
    """Migrate existing models to have proper model_type field"""
    session = get_session()
    try:
        # Update all models without model_type to be 'local'
        result = session.execute(
            text("UPDATE models SET model_type = 'local' WHERE model_type IS NULL OR model_type = ''")
        )
        models_updated = getattr(result, 'rowcount', 0)
        session.commit()
        
        return {
            "success": True,
            "models_updated": models_updated,
            "message": f"Updated {models_updated} models to have model_type='local'"
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════
# 🏢 RUTAS DE CONFIGURACIÓN DE NEGOCIO
# ═══════════════════════════════════════════════════════════════

@app.get("/api/business/config")
async def get_business_config():
    """Obtiene la configuración actual del negocio"""
    try:
        return JSONResponse(content=business_config.config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/business/config")
async def update_business_config(data: dict):
    """Actualiza la configuración completa del negocio"""
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

@app.post("/api/business/config/field")
async def update_business_field(data: dict):
    """Actualiza un campo específico de la configuración"""
    try:
        field_path = data.get("field")
        value = data.get("value")
        
        if not field_path:
            raise HTTPException(status_code=400, detail="Campo 'field' requerido")
        
        if business_config.update_field(field_path, value):
            return JSONResponse(content={
                "success": True, 
                "message": f"Campo {field_path} actualizado"
            })
        else:
            raise HTTPException(status_code=500, detail="Error actualizando campo")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/business/fields")
async def get_editable_fields():
    """Obtiene la lista de campos editables con sus metadatos"""
    try:
        return JSONResponse(content=business_config.get_editable_fields())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/business/config/export")
async def export_business_config():
    """Exporta la configuración como archivo JSON"""
    try:
        config_json = business_config.export_config()
        
        return StreamingResponse(
            io.StringIO(config_json),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=business_config.json"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/business/config/import")
async def import_business_config(file: UploadFile = File(...)):
    """Importa configuración desde archivo JSON"""
    try:
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="Solo se permiten archivos JSON")
        
        content = await file.read()
        config_json = content.decode('utf-8')
        
        if business_config.import_config(config_json):
            return JSONResponse(content={
                "success": True, 
                "message": "Configuración importada exitosamente"
            })
        else:
            raise HTTPException(status_code=500, detail="Error importando configuración")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/business/config/reset")
async def reset_business_config():
    """Reinicia la configuración a los valores por defecto"""
    try:
        default_config = business_config.get_default_config()
        business_config.config = default_config
        
        if business_config.save_config(default_config):
            return JSONResponse(content={
                "success": True, 
                "message": "Configuración reiniciada a valores por defecto"
            })
        else:
            raise HTTPException(status_code=500, detail="Error reiniciando configuración")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/business/preview")
async def preview_business_config():
    """Previsualiza cómo se verá el payload generado"""
    try:
        # Simular actualización de payloads sin guardar
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


# ============== AUDIT SYSTEM API ==============

@app.get('/api/audit/logs')
async def get_audit_logs(
    username: Optional[str] = None,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Obtener logs de auditoría (solo admin)"""
    try:
        logs = audit_manager.get_logs(
            username=username,
            action=action,
            resource=resource,
            limit=limit,
            offset=offset
        )
        return {"logs": logs, "count": len(logs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/audit/stats')
async def get_audit_stats(current_user: Dict[str, Any] = Depends(require_admin)):
    """Obtener estadísticas de auditoría (solo admin)"""
    try:
        stats = audit_manager.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== CAMPAIGN MANAGEMENT API ==============

@app.get('/api/campaigns/{campaign_id}')
async def get_campaign_status(campaign_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Obtener estado de una campaña"""
    try:
        status = queue_manager.get_campaign_status(campaign_id)
        if not status:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/campaigns/{campaign_id}/pause')
async def pause_campaign(campaign_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Pausar una campaña"""
    try:
        success = queue_manager.pause_campaign(campaign_id)
        if not success:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
        return {"success": True, "message": f"Campaña {campaign_id} pausada"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/campaigns/{campaign_id}/resume')
async def resume_campaign(campaign_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Reanudar una campaña"""
    try:
        success = queue_manager.resume_campaign(campaign_id)
        if not success:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
        return {"success": True, "message": f"Campaña {campaign_id} reanudada"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete('/api/campaigns/{campaign_id}')
async def cancel_campaign(campaign_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Cancelar una campaña"""
    try:
        success = queue_manager.cancel_campaign(campaign_id)
        if not success:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
        return {"success": True, "message": f"Campaña {campaign_id} cancelada"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== ALERT SYSTEM API ==============

@app.get('/api/alerts')
async def get_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    chat_id: Optional[str] = None,
    assigned_to: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Obtener alertas con filtros"""
    try:
        alerts = alert_manager.get_alerts(
            status=status,
            severity=severity,
            chat_id=chat_id,
            assigned_to=assigned_to,
            limit=limit,
            offset=offset
        )
        return {"alerts": alerts, "count": len(alerts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put('/api/alerts/{alert_id}/assign')
async def assign_alert(
    alert_id: str,
    assigned_to: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Asignar una alerta a un operador"""
    try:
        success = alert_manager.assign_alert(alert_id, assigned_to)
        if not success:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")
        return {"success": True, "message": f"Alerta asignada a {assigned_to}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put('/api/alerts/{alert_id}/resolve')
async def resolve_alert(
    alert_id: str,
    notes: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Resolver una alerta"""
    try:
        success = alert_manager.resolve_alert(alert_id, notes)
        if not success:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")
        return {"success": True, "message": "Alerta resuelta"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/alert-rules')
async def get_alert_rules(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Obtener todas las reglas de alerta"""
    try:
        rules = alert_manager.get_rules()
        return {"rules": rules, "count": len(rules)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AlertRuleCreate(BaseModel):
    name: str
    rule_type: str
    pattern: str
    severity: str
    actions: List[str]
    enabled: Optional[bool] = True
    schedule: Optional[Dict] = None
    metadata: Optional[Dict] = None


@app.post('/api/alert-rules')
async def create_alert_rule(
    rule: AlertRuleCreate,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Crear una regla de alerta (solo admin)"""
    try:
        rule_id = alert_manager.create_rule(
            name=rule.name,
            rule_type=rule.rule_type,
            pattern=rule.pattern,
            severity=rule.severity,
            actions=rule.actions,
            created_by=current_user.get("username", "unknown"),
            enabled=rule.enabled,
            schedule=rule.schedule,
            metadata=rule.metadata
        )
        
        if not rule_id:
            raise HTTPException(status_code=500, detail="Error creando regla")
        
        return {"success": True, "rule_id": rule_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put('/api/alert-rules/{rule_id}')
async def update_alert_rule(
    rule_id: int,
    updates: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Actualizar una regla de alerta (solo admin)"""
    try:
        success = alert_manager.update_rule(rule_id, **updates)
        if not success:
            raise HTTPException(status_code=404, detail="Regla no encontrada")
        return {"success": True, "message": "Regla actualizada"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete('/api/alert-rules/{rule_id}')
async def delete_alert_rule(
    rule_id: int,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Eliminar una regla de alerta (solo admin)"""
    try:
        success = alert_manager.delete_rule(rule_id)
        if not success:
            raise HTTPException(status_code=404, detail="Regla no encontrada")
        return {"success": True, "message": "Regla eliminada"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== WHATSAPP CLOUD API WEBHOOKS ==============

@app.get('/webhooks/whatsapp')
async def whatsapp_webhook_verify(request: Request):
    """Verificación de webhook de WhatsApp Cloud API"""
    try:
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")
        
        if not mode or not token:
            raise HTTPException(status_code=400, detail="Missing parameters")
        
        verified_challenge = verify_webhook(mode, token, challenge)
        
        if verified_challenge:
            return JSONResponse(content=int(verified_challenge), media_type="text/plain")
        else:
            raise HTTPException(status_code=403, detail="Verification failed")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en verificación de webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/webhooks/whatsapp')
async def whatsapp_webhook_receive(request: Request):
    """Recepción de mensajes de WhatsApp Cloud API"""
    try:
        body = await request.json()
        
        # Obtener provider
        provider = get_provider()
        
        # Normalizar mensaje
        normalized_msg = provider.receive_message(body)
        
        if not normalized_msg:
            return {"status": "ok", "message": "No processable message"}
        
        logger.info(f"📨 Mensaje recibido via Cloud API de {normalized_msg.chat_id}")
        
        # Verificar alertas
        if normalized_msg.text:
            alert_manager.check_alert_rules(
                normalized_msg.text,
                normalized_msg.chat_id,
                {"provider": "cloud"}
            )
        
        # Procesar mensaje (integrar con el pipeline de chat)
        # TODO: Llamar a stub_chat o el sistema de respuesta
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"❌ Error procesando webhook de WhatsApp: {e}")
        # Retornar 200 para que Meta no reintente
        return {"status": "error", "message": str(e)}


@app.get('/api/whatsapp/provider/status')
async def get_whatsapp_provider_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Obtener estado del proveedor de WhatsApp actual"""
    try:
        provider = get_provider()
        status = provider.get_status()
        
        mode = os.environ.get("WHATSAPP_MODE", "web")
        
        return {
            "mode": mode,
            "status": status,
            "available": provider.is_available()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    print("Starting Chatbot Admin Panel on http://127.0.0.1:8003")
    print("Dashboard: http://127.0.0.1:8003/ui/index.html")
    print("Quick Chat: http://127.0.0.1:8003/chat")
    uvicorn.run(app, host="127.0.0.1", port=8003, reload=False)