"""System/process control admin routes extracted from admin_panel."""

import os
import socket
import subprocess
import time
from typing import Any

from fastapi import APIRouter, Depends

from src.services.auth_system import get_current_user, require_admin
from src.services.process_control import kill_by_port, kill_processes, kill_processes_except_current

router = APIRouter(tags=["system-admin"])

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None


@router.get("/api/system/check-processes")
def api_system_check_processes(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Verificar qué procesos problemáticos están corriendo ANTES de la limpieza."""
    try:
        problematic_processes = []

        if psutil:
            targets = [
                "LM Studio.exe",
                "lms.exe",
                "lmstudio.exe",
                "chrome.exe",
                "chromium.exe",
                "msedge.exe",
                "python.exe",
                "python3.exe",
                "python3.13.exe",
                "whatsapp_automator.py",
            ]

            for proc in psutil.process_iter(["pid", "name", "cmdline", "memory_info"]):
                try:
                    name = (proc.info.get("name") or "").lower()
                    cmdline = " ".join(proc.info.get("cmdline") or []).lower()

                    for target in targets:
                        if target.lower() in name or target.lower() in cmdline:
                            memory_mb = 0
                            try:
                                mem_info = proc.info.get("memory_info")
                                if mem_info:
                                    memory_mb = mem_info.rss // (1024 * 1024)
                            except Exception:
                                pass

                            problematic_processes.append(
                                {
                                    "pid": proc.info["pid"],
                                    "name": proc.info.get("name", "unknown"),
                                    "target_match": target,
                                    "memory_mb": memory_mb,
                                    "cmdline_snippet": cmdline[:100] + "..." if len(cmdline) > 100 else cmdline,
                                }
                            )
                            break

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        ports_status = {}
        for port in [1234, 8000, 8001, 8002, 8003]:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    ports_status[port] = "OCUPADO"
            except OSError:
                ports_status[port] = "LIBRE"

        return {
            "success": True,
            "problematic_processes": problematic_processes,
            "total_problematic": len(problematic_processes),
            "ports_status": ports_status,
            "needs_cleanup": len(problematic_processes) > 0
            or any(status == "OCUPADO" for status in ports_status.values()),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/api/system/stop-all")
def api_system_stop_all(current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """STOP NUCLEAR: mata procesos problemáticos preservando el admin panel actual."""
    try:
        killed = []
        results = []

        if psutil:
            lm_processes = ["LM Studio.exe", "lms.exe", "lms", "lm-studio", "lmstudio.exe"]
            for process_name in lm_processes:
                pids = kill_processes([process_name])
                if pids:
                    killed.extend(pids)
                    results.append(f"psutil: Matados {len(pids)} procesos de {process_name}")

            browser_processes = ["chrome.exe", "chromium.exe", "msedge.exe"]
            for process_name in browser_processes:
                pids = kill_processes([process_name])
                if pids:
                    killed.extend(pids)
                    results.append(f"psutil: Matados {len(pids)} procesos de {process_name}")

            current_pid = os.getpid()
            python_processes = ["python.exe", "python3.exe", "python3.13.exe", "pythonw.exe"]
            for process_name in python_processes:
                pids = kill_processes_except_current([process_name], current_pid)
                if pids:
                    killed.extend(pids)
                    results.append(f"psutil: Matados {len(pids)} procesos de {process_name} (excluyendo admin panel)")

            wa_pids = kill_processes(["whatsapp_automator.py"])
            if wa_pids:
                killed.extend(wa_pids)
                results.append(f"psutil: Matados {len(wa_pids)} procesos WhatsApp automator")

        try:
            taskkill_commands = [
                ["taskkill", "/f", "/im", "LM Studio.exe"],
                ["taskkill", "/f", "/im", "lms.exe"],
                ["taskkill", "/f", "/im", "chrome.exe"],
                ["taskkill", "/f", "/im", "chromium.exe"],
                ["taskkill", "/f", "/im", "msedge.exe"],
            ]

            for cmd in taskkill_commands:
                try:
                    result = subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=10)
                    if "SUCCESS" in result.stdout:
                        lines = result.stdout.count("SUCCESS")
                        results.append(f"taskkill: Matados {lines} procesos con {cmd[3]}")
                except subprocess.TimeoutExpired:
                    results.append(f"taskkill: Timeout en {' '.join(cmd)}")
                except Exception as e:
                    results.append(f"taskkill: Error en {' '.join(cmd)}: {e}")

        except Exception as e:
            results.append(f"taskkill: Error general: {e}")

        ports_to_kill = [1234, 8000, 8001, 8002]
        for port in ports_to_kill:
            port_pids = kill_by_port(port)
            if port_pids:
                killed.extend(port_pids)
                results.append(f"puerto: Matados {len(port_pids)} procesos en puerto {port}")

        time.sleep(2)

        ports_status = {}
        for port in [1234, 8003]:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    ports_status[port] = "OCUPADO ⚠️"
            except OSError:
                ports_status[port] = "LIBRE ✅"

        return {
            "success": True,
            "total_killed_pids": len(set(killed)),
            "unique_killed_pids": list(set(killed)),
            "actions": results,
            "ports_status": ports_status,
            "message": f"🧹 LIMPIEZA NUCLEAR COMPLETADA - {len(set(killed))} procesos eliminados",
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
