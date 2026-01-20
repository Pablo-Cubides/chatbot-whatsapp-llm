"""
🔧 Utilidades Core del Sistema
Funciones de utilidad para procesos, puertos, archivos, etc.
"""

import os
import json
import socket
import logging
from typing import List, Optional, Any
from string import Template as StrTemplate

logger = logging.getLogger(__name__)

# Importación condicional de psutil
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False


def is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """Verifica si un puerto está abierto."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def get_lm_port() -> int:
    """Obtiene el puerto de LM Studio desde variable de entorno."""
    try:
        return int(os.environ.get('LM_STUDIO_PORT', '1234'))
    except Exception:
        return 1234


def kill_processes(matchers: List[str]) -> List[int]:
    """
    Termina procesos cuyo nombre o cmdline contiene cualquiera de los matchers.
    Retorna lista de PIDs terminados.
    """
    killed = []
    if not PSUTIL_AVAILABLE:
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
    
    # Esperar y forzar si es necesario
    _wait_and_force_kill(killed)
    return killed


def kill_processes_except_current(matchers: List[str], exclude_pid: int) -> List[int]:
    """
    Termina procesos excepto el PID especificado.
    Retorna lista de PIDs terminados.
    """
    killed = []
    if not PSUTIL_AVAILABLE:
        return killed
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['pid'] == exclude_pid:
                continue
            
            name = (proc.info.get('name') or '').lower()
            cmdline = ' '.join(proc.info.get('cmdline') or []).lower()
            if any(m.lower() in name or m.lower() in cmdline for m in matchers):
                proc.terminate()
                killed.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    _wait_and_force_kill(killed)
    return killed


def kill_by_port(port: int) -> List[int]:
    """Termina procesos escuchando en un puerto específico."""
    killed = []
    if not PSUTIL_AVAILABLE:
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
        
        _wait_and_force_kill(killed)
    except Exception as e:
        logger.error(f"Error killing processes on port {port}: {e}")
    
    return list(set(killed))


def _wait_and_force_kill(pids: List[int]) -> None:
    """Helper para esperar y forzar kill de procesos."""
    if not PSUTIL_AVAILABLE or not pids:
        return
    
    try:
        psutil.wait_procs(
            [psutil.Process(pid) for pid in pids if psutil.pid_exists(pid)],
            timeout=2
        )
    except Exception:
        pass
    
    for pid in pids:
        try:
            if psutil.pid_exists(pid):
                psutil.Process(pid).kill()
        except Exception:
            pass


def script_match_in_cmdline(proc, script_name: str) -> bool:
    """Verifica si el cmdline del proceso referencia un script."""
    try:
        parts = proc.info.get('cmdline') or []
        if not parts:
            return False
        cmd = ' '.join(str(x) for x in parts)
        cmd_low = cmd.lower().replace('\\', '/')
        
        if script_name.lower() in cmd_low:
            return True
        
        here = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        abs_path = os.path.join(here, script_name).replace('\\', '/').lower()
        return abs_path in cmd_low
    except Exception:
        return False


def get_playwright_profile_dir() -> str:
    """Lee el directorio de perfil de Playwright desde config."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        cfg_path = os.path.join(base_dir, 'config', 'playwright_config.json')
        
        if not os.path.exists(cfg_path):
            return ''
        
        with open(cfg_path, 'r', encoding='utf-8') as f:
            raw = f.read()
        
        try:
            raw = StrTemplate(raw).substitute(os.environ)
        except Exception:
            pass
        
        data = json.loads(raw)
        return data.get('userDataDir') or ''
    except Exception:
        return ''


def kill_browser_profile_processes() -> List[int]:
    """Termina procesos de navegador vinculados al perfil de Playwright."""
    killed = []
    if not PSUTIL_AVAILABLE:
        return killed
    
    profile = get_playwright_profile_dir()
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
    
    _wait_and_force_kill(killed)
    return list(set(killed))


def load_json_config(filename: str, default: Optional[dict] = None) -> dict:
    """Carga un archivo JSON de configuración."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        filepath = os.path.join(base_dir, filename)
        
        if not os.path.exists(filepath):
            return default or {}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {filename}: {e}")
        return default or {}


def save_json_config(filename: str, data: dict) -> bool:
    """Guarda un archivo JSON de configuración."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        filepath = os.path.join(base_dir, filename)
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving {filename}: {e}")
        return False
