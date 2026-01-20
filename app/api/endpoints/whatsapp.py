"""
📱 Endpoints de WhatsApp y Modelos LLM
Gestión de proveedores de WhatsApp y modelos de IA locales.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import json
import socket
import glob
import requests as http_requests
import logging

from src.services.auth_system import get_current_user, require_admin
from src.services.whatsapp_provider import get_provider
from app.core.utils import (
    is_port_open, 
    get_lm_port, 
    kill_processes, 
    kill_browser_profile_processes
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["WhatsApp & LLM"])


# =====================================
# WhatsApp Endpoints
# =====================================

@router.get("/whatsapp/status")
async def get_whatsapp_status(current_user: dict = Depends(get_current_user)):
    """
    Obtiene el estado actual de la conexión de WhatsApp.
    """
    try:
        provider = get_provider()
        status = await provider.get_status() if provider else {"connected": False}
        
        return {
            "status": "success",
            "whatsapp": status,
            "mode": os.environ.get("WHATSAPP_MODE", "web")
        }
    except Exception as e:
        logger.error(f"Error getting WhatsApp status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "whatsapp": {"connected": False}
        }


@router.post("/whatsapp/connect")
async def connect_whatsapp(current_user: dict = Depends(require_admin)):
    """
    Inicia la conexión de WhatsApp (solo admin).
    """
    try:
        # TODO: Implementar lógica de conexión
        return {
            "status": "success",
            "message": "Iniciando conexión de WhatsApp..."
        }
    except Exception as e:
        logger.error(f"Error connecting WhatsApp: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/whatsapp/disconnect")
async def disconnect_whatsapp(current_user: dict = Depends(require_admin)):
    """
    Desconecta WhatsApp y cierra procesos del navegador.
    """
    try:
        killed = kill_browser_profile_processes()
        return {
            "status": "success",
            "message": "WhatsApp desconectado",
            "processes_killed": len(killed)
        }
    except Exception as e:
        logger.error(f"Error disconnecting WhatsApp: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================
# LM Studio / Modelos Locales
# =====================================

def _filter_and_categorize_models(models: List[Dict]) -> Dict[str, List]:
    """Filtra y categoriza modelos según criterios específicos."""
    
    # Modelos principales permitidos
    allowed_main_models = [
        'nemotron-mini-4b-instruct',
        'meta-llama-3.1-8b-instruct', 
        'phi-4'
    ]
    
    # Modelos razonadores permitidos
    allowed_reasoning_models = [
        'deepseek-r1-distill-qwen-7b',
        'openai/gpt-oss-20b'
    ]
    
    main_models = []
    reasoning_models = []
    hidden_models = []
    other_models = []
    
    for model in models:
        model_name = model.get('id', '').lower()
        
        if model_name in allowed_main_models:
            main_models.append({**model, 'category': 'main'})
        elif model_name in allowed_reasoning_models:
            reasoning_models.append({**model, 'category': 'reasoning'})
        elif 'embed' in model_name or 'embedding' in model_name:
            hidden_models.append({**model, 'category': 'hidden'})
        else:
            other_models.append({**model, 'category': 'other'})
    
    return {
        'main_models': main_models,
        'reasoning_models': reasoning_models, 
        'hidden_models': hidden_models,
        'other_models': other_models,
        'all_available': other_models + hidden_models
    }


@router.get("/lmstudio/models")
async def get_lmstudio_models(current_user: dict = Depends(get_current_user)):
    """
    Obtiene modelos disponibles de LM Studio.
    """
    port = get_lm_port()
    lm_running = is_port_open('127.0.0.1', port)
    
    models = []
    api_error = None
    
    if lm_running:
        try:
            resp = http_requests.get(f"http://127.0.0.1:{port}/v1/models", timeout=3)
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
                api_error = f"LM Studio respondió {resp.status_code}"
        except Exception as e:
            api_error = str(e)
    
    # Escanear modelos locales
    models_dir = os.environ.get('MODELS_DIR') or (
        r'D:\IA\Texto\Models' if os.name == 'nt' else '/mnt/d/IA/Texto/Models'
    )
    local_models = []
    
    try:
        if os.path.isdir(models_dir):
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
        pass
    
    # Combinar y categorizar
    all_models = models + local_models
    categorized = _filter_and_categorize_models(all_models)
    
    # Obtener modelo actual
    current_model = "ninguno"
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        payload_path = os.path.join(base_dir, 'payload.json')
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
            result['note'] = 'LM Studio no respondió, mostrando modelos locales.'
        else:
            result['note'] = 'LM Studio no respondió y no hay modelos locales.'
    
    return result


class SwitchModelRequest(BaseModel):
    model_id: str


@router.post("/lmstudio/switch-model")
async def switch_lmstudio_model(
    request: SwitchModelRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Cambia el modelo activo en LM Studio.
    """
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        payload_path = os.path.join(base_dir, 'payload.json')
        
        with open(payload_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        
        old_model = payload.get('model', 'unknown')
        payload['model'] = request.model_id
        
        with open(payload_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
        
        return {
            "status": "success",
            "message": f"Modelo cambiado de '{old_model}' a '{request.model_id}'",
            "old_model": old_model,
            "new_model": request.model_id
        }
    except Exception as e:
        logger.error(f"Error switching model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lmstudio/start")
async def start_lmstudio(current_user: dict = Depends(require_admin)):
    """
    Intenta iniciar LM Studio (solo Windows).
    """
    port = get_lm_port()
    
    if is_port_open('127.0.0.1', port):
        return {
            "status": "success",
            "message": f"LM Studio ya está activo en puerto {port}",
            "port": port
        }
    
    # Buscar ejecutable
    candidates = []
    env_exe = os.environ.get('LM_STUDIO_EXE')
    if env_exe:
        candidates.append(env_exe)
    
    if os.name == 'nt':
        candidates.extend([
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\LM Studio\LM Studio.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\lm-studio\LM Studio.exe"),
            r"C:\Program Files\LM Studio\LM Studio.exe",
            r"D:\IA\Texto\Lmstudio\LM Studio.exe",
        ])
    
    exe_path = None
    for p in candidates:
        if p and os.path.isfile(p):
            exe_path = p
            break
    
    if not exe_path:
        return {
            "status": "error",
            "message": "No se encontró ejecutable de LM Studio",
            "candidates": candidates
        }
    
    try:
        import subprocess
        subprocess.Popen([exe_path], shell=False, start_new_session=True)
        
        return {
            "status": "success",
            "message": f"LM Studio iniciado desde {exe_path}",
            "port": port
        }
    except Exception as e:
        logger.error(f"Error starting LM Studio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lmstudio/stop")
async def stop_lmstudio(current_user: dict = Depends(require_admin)):
    """
    Detiene LM Studio.
    """
    try:
        killed = kill_processes(['LM Studio', 'lm-studio', 'lmstudio'])
        return {
            "status": "success",
            "message": f"Procesos LM Studio terminados: {len(killed)}",
            "killed_pids": killed
        }
    except Exception as e:
        logger.error(f"Error stopping LM Studio: {e}")
        raise HTTPException(status_code=500, detail=str(e))
