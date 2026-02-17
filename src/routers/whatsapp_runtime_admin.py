"""WhatsApp runtime control routes extracted from admin_panel."""

import json
import os
import subprocess
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, Depends

from src.routers.lmstudio_admin import get_lmstudio_local_models_info
from src.services.auth_system import get_current_user, require_admin

router = APIRouter(tags=["whatsapp-runtime-admin"])

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None


def _script_match_in_cmdline(proc, script_name: str) -> bool:
    """Return True if process cmdline references script by name or absolute path."""
    try:
        parts = proc.info.get("cmdline") or []
        if not parts:
            return False
        cmd = " ".join(str(x) for x in parts)
        cmd_low = cmd.lower().replace("\\", "/")
        if script_name.lower() in cmd_low:
            return True
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        abs_path = os.path.join(root, script_name).replace("\\", "/").lower()
        return abs_path in cmd_low
    except Exception:
        return False


def _get_playwright_profile_dir() -> str:
    """Read Playwright userDataDir from config/playwright_config.json if available."""
    try:
        cfg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config", "playwright_config.json"))
        if not os.path.exists(cfg_path):
            return ""

        with open(cfg_path, encoding="utf-8") as f:
            raw = f.read()

        with suppress(Exception):
            from string import Template as StrTemplate

            raw = StrTemplate(raw).substitute(os.environ)

        data = json.loads(raw)
        return data.get("userDataDir") or ""
    except Exception:
        return ""


def _kill_browser_profile_processes() -> list[int]:
    """Kill Chromium/Edge/Chrome processes bound to Playwright userDataDir."""
    killed: list[int] = []
    if psutil is None:
        return killed

    profile = _get_playwright_profile_dir()
    if not profile:
        return killed

    prof_norm = profile.lower().replace("\\", "/").strip()
    targets = ["chrome.exe", "msedge.exe", "chromium.exe", "chrome", "msedge", "chromium"]

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (proc.info.get("name") or "").lower()
            cmd = " ".join(proc.info.get("cmdline") or []).lower().replace("\\", "/")
            if any(t in name for t in targets) and (prof_norm and prof_norm in cmd):
                proc.terminate()
                killed.append(proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    with suppress(Exception):
        psutil.wait_procs([psutil.Process(pid) for pid in killed if psutil.pid_exists(pid)], timeout=2)

    for pid in list(killed):
        with suppress(Exception):
            if psutil.pid_exists(pid):
                psutil.Process(pid).kill()

    return list(set(killed))


def get_whatsapp_runtime_status() -> dict[str, Any]:
    """Compute runtime status for WhatsApp automator and browser profile leftovers."""
    try:
        if psutil is None:
            return {"status": "error", "error": "psutil not available"}

        automator_pid = None
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if _script_match_in_cmdline(proc, "whatsapp_automator.py"):
                    automator_pid = proc.info["pid"]
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        browser_pids: list[int] = []
        profile = _get_playwright_profile_dir()
        prof_norm = profile.lower().replace("\\", "/").strip() if profile else ""
        targets = ["chrome.exe", "msedge.exe", "chromium.exe", "chrome", "msedge", "chromium"]
        if prof_norm:
            for process in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    name = (process.info.get("name") or "").lower()
                    cmd = " ".join(process.info.get("cmdline") or []).lower().replace("\\", "/")
                    if any(t in name for t in targets) and prof_norm in cmd:
                        browser_pids.append(process.info["pid"])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        if automator_pid:
            return {"status": "running", "pid": automator_pid, "browser_pids": browser_pids}
        if browser_pids:
            return {"status": "stale-browser", "pid": None, "browser_pids": browser_pids}
        return {"status": "stopped", "pid": None, "browser_pids": []}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/api/whatsapp/status")
def api_whatsapp_status(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Check if WhatsApp automator is running."""
    return get_whatsapp_runtime_status()


@router.post("/api/whatsapp/start")
def api_whatsapp_start(current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Start WhatsApp automator with LM Studio validation."""
    try:
        lm_status = get_lmstudio_local_models_info()
        if not lm_status.get("lm_studio_running", False):
            return {
                "success": False,
                "error": "LM Studio no está ejecutándose. Inicia el servidor en puerto 1234 antes de continuar.",
            }

        if not lm_status.get("models") or len(lm_status.get("models", [])) == 0:
            return {
                "success": False,
                "error": "No hay modelos cargados en LM Studio. Carga un modelo antes de iniciar WhatsApp.",
            }

        status = get_whatsapp_runtime_status()
        if status.get("status") == "running":
            return {"success": False, "error": "WhatsApp automator already running"}

        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        script_path = os.path.join(root, "whatsapp_automator.py")
        venv_python = os.path.join(root, "venv", "Scripts", "python.exe")
        python_cmd = venv_python if os.path.exists(venv_python) else "python"

        env = os.environ.copy()
        env["KEEP_AUTOMATOR_OPEN"] = "true"

        try:
            log_dir = os.path.join(root, "logs")
            os.makedirs(log_dir, exist_ok=True)
            start_log = os.path.join(log_dir, "whatsapp_start.log")
            stdout_f = open(start_log, "a", encoding="utf-8")
            stderr_f = stdout_f
        except Exception:
            stdout_f = subprocess.DEVNULL
            stderr_f = subprocess.DEVNULL

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)

        import sys
        import time

        if not os.path.exists(python_cmd):
            python_cmd = sys.executable or python_cmd

        proc = subprocess.Popen(
            [python_cmd, script_path],
            cwd=root,
            env=env,
            stdout=stdout_f,
            stderr=stderr_f,
            close_fds=True,
            creationflags=creationflags,
        )

        time.sleep(1)
        return {"success": True, "pid": proc.pid, "message": "WhatsApp automator started"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/api/whatsapp/stop")
def api_whatsapp_stop(current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Stop WhatsApp automator."""
    try:
        if psutil is None:
            return {"success": False, "error": "psutil not available"}

        stopped_pids: list[int] = []
        targets = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if _script_match_in_cmdline(proc, "whatsapp_automator.py"):
                    targets.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        for proc in targets:
            with suppress(Exception):
                proc.terminate()

        with suppress(Exception):
            psutil.wait_procs(targets, timeout=3)

        for proc in targets:
            try:
                if psutil.pid_exists(proc.pid):
                    proc.kill()
                stopped_pids.append(proc.pid)
            except Exception:
                pass

        with suppress(Exception):
            stopped_pids.extend(_kill_browser_profile_processes())

        if stopped_pids:
            return {
                "success": True,
                "stopped_pids": stopped_pids,
                "message": f"Stopped {len(stopped_pids)} processes",
            }
        return {"success": True, "message": "No WhatsApp automator process found (may already be stopped)"}
    except Exception as e:
        return {"success": False, "error": str(e)}
