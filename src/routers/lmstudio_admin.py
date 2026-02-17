"""LM Studio admin routes extracted from admin_panel."""

import json
import os
import subprocess
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from src.services.auth_system import get_current_user, require_admin
from src.services.process_control import kill_by_port, kill_processes, lm_port

router = APIRouter(tags=["lmstudio-admin"])


def _filter_and_categorize_models(models: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Filtra y categoriza modelos según listas permitidas."""
    allowed_main_models = ["nemotron-mini-4b-instruct", "meta-llama-3.1-8b-instruct", "phi-4"]
    allowed_reasoning_models = ["deepseek-r1-distill-qwen-7b", "openai/gpt-oss-20b"]

    main_models: list[dict[str, Any]] = []
    reasoning_models: list[dict[str, Any]] = []
    hidden_models: list[dict[str, Any]] = []
    other_models: list[dict[str, Any]] = []

    for model in models:
        model_name = model.get("id", "").lower()
        if model_name in allowed_main_models:
            main_models.append({**model, "category": "main"})
        elif model_name in allowed_reasoning_models:
            reasoning_models.append({**model, "category": "reasoning"})
        elif "embed" in model_name or "embedding" in model_name:
            hidden_models.append({**model, "category": "hidden"})
        else:
            other_models.append({**model, "category": "other"})

    return {
        "main_models": main_models,
        "reasoning_models": reasoning_models,
        "hidden_models": hidden_models,
        "other_models": other_models,
        "all_available": other_models + hidden_models,
    }


def get_lmstudio_models_info() -> dict[str, Any]:
    """Get LM Studio models with local fallback and category filtering."""
    import glob
    import socket

    def _is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    port = lm_port()
    lm_running = _is_port_open("127.0.0.1", port)

    models: list[dict[str, Any]] = []
    api_error = None
    if lm_running:
        try:
            resp = httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                for model in data.get("data", []):
                    models.append(
                        {
                            "id": model.get("id", "unknown"),
                            "name": model.get("id", "unknown"),
                            "object": model.get("object", "model"),
                            "source": "lmstudio",
                        }
                    )
            else:
                api_error = f"LM Studio respondió {resp.status_code} en /v1/models"
        except httpx.HTTPError as e:
            api_error = str(e)

    models_dir = os.environ.get("MODELS_DIR") or (r"D:\IA\Texto\Models" if os.name == "nt" else "/mnt/d/IA/Texto/Models")
    local_models: list[dict[str, Any]] = []
    try:
        if os.path.isdir(models_dir):
            pattern = os.path.join(models_dir, "**", "*.gguf")
            for path in glob.iglob(pattern, recursive=True):
                name = os.path.splitext(os.path.basename(path))[0]
                local_models.append({"id": name, "name": name, "path": path, "source": "local"})
    except Exception:
        pass

    categorized = _filter_and_categorize_models(models + local_models)

    current_model = "ninguno"
    try:
        payload_path = os.path.join(os.path.dirname(__file__), "..", "..", "payload.json")
        payload_path = os.path.abspath(payload_path)
        with open(payload_path, encoding="utf-8") as f:
            payload = json.load(f)
            current_model = payload.get("model", "ninguno")
    except Exception:
        pass

    result: dict[str, Any] = {
        "status": "success",
        "lm_studio_running": bool(lm_running),
        "main_models": categorized["main_models"],
        "reasoning_models": categorized["reasoning_models"],
        "available_for_add": categorized["all_available"],
        "current_model": current_model,
        "port": port,
    }

    if api_error and not models:
        result["status"] = "error"
        result["error"] = api_error
        result["note"] = (
            "LM Studio no respondió /v1/models, mostrando modelos locales encontrados."
            if local_models
            else "LM Studio no respondió y no se encontraron modelos locales."
        )

    return result


def get_lmstudio_local_models_info() -> dict[str, Any]:
    """Compatibility payload used by existing UI for local-only model selector."""
    result = get_lmstudio_models_info()

    if result.get("status") == "error":
        return {
            "status": "error",
            "models": [],
            "local_models": [],
            "lm_studio_running": False,
            "error": result.get("error", "Error desconocido"),
            "note": "No se detectó LM Studio ni modelos locales. Inicia LM Studio en 127.0.0.1:1234 o contacta soporte.",
        }

    main_models = result.get("main_models", [])
    reasoning_models = result.get("reasoning_models", [])
    all_filtered = main_models + reasoning_models

    return {
        "status": "success",
        "lm_studio_running": result.get("lm_studio_running", False),
        "models": main_models,
        "reasoning_models": reasoning_models,
        "local_models": [],
        "port": result.get("port", 1234),
        "current_model": result.get("current_model", "ninguno"),
        "main_models_count": len(main_models),
        "reasoning_models_count": len(reasoning_models),
        "note": f"Mostrando {len(all_filtered)} modelos permitidos: {len(main_models)} principales + {len(reasoning_models)} razonadores"
        if all_filtered
        else "No hay modelos permitidos cargados. Inicia LM Studio y carga un modelo de la lista permitida.",
    }


@router.get("/api/lmstudio/models")
def api_lmstudio_models(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Lista modelos detectados en LM Studio y en disco local."""
    return get_lmstudio_models_info()


@router.get("/api/lmstudio/models/local-only")
def api_lmstudio_local_models(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Retorna payload de compatibilidad para selector local-only de UI."""
    return get_lmstudio_local_models_info()


@router.post("/api/lmstudio/add-model")
async def api_lmstudio_add_model(request: Request, current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Agregar modelo manualmente a lista principal o razonadores."""
    try:
        body = await request.json()
        model_id = body.get("model_id")
        target_list = body.get("target_list", "main")

        if not model_id:
            return {"success": False, "error": "model_id requerido"}
        if target_list not in ["main", "reasoning"]:
            return {"success": False, "error": "target_list debe ser 'main' o 'reasoning'"}

        models_response = get_lmstudio_models_info()
        available_models = models_response.get("available_for_add", [])
        selected_model = next((model for model in available_models if model["id"] == model_id), None)
        if not selected_model:
            return {"success": False, "error": f"Modelo {model_id} no disponible para agregar"}

        payload_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "payload.json"))
        with open(payload_path, encoding="utf-8") as f:
            payload = json.load(f)

        old_model = payload.get("model", "unknown")
        payload["model"] = model_id

        with open(payload_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)

        return {
            "success": True,
            "message": f"Modelo '{model_id}' agregado a lista {target_list} y activado",
            "old_model": old_model,
            "new_model": model_id,
            "target_list": target_list,
            "note": "NOTA: Para que aparezca permanentemente en la lista, contacta al desarrollador",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/api/lmstudio/switch-model")
async def api_lmstudio_switch_model(request: Request, current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Cambiar entre modelos ya permitidos en las listas."""
    try:
        body = await request.json()
        model_id = body.get("model_id")
        if not model_id:
            return {"success": False, "error": "model_id requerido"}

        models_response = get_lmstudio_models_info()
        allowed_models = [m["id"] for m in models_response.get("main_models", []) + models_response.get("reasoning_models", [])]
        if model_id not in allowed_models:
            return {"success": False, "error": f"Modelo {model_id} no está en listas permitidas"}

        payload_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "payload.json"))
        with open(payload_path, encoding="utf-8") as f:
            payload = json.load(f)

        old_model = payload.get("model", "unknown")
        payload["model"] = model_id

        with open(payload_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)

        return {
            "success": True,
            "message": f"Modelo cambiado de '{old_model}' a '{model_id}'",
            "old_model": old_model,
            "new_model": model_id,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/api/lmstudio/start")
def api_lmstudio_start(current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Attempt to start LM Studio GUI app on Windows and wait for local server port."""
    try:
        import socket
        import time

        port = lm_port()

        def _is_port_open(host: str, test_port: int, timeout: float = 0.5) -> bool:
            try:
                with socket.create_connection((host, test_port), timeout=timeout):
                    return True
            except OSError:
                return False

        if _is_port_open("127.0.0.1", port):
            return {"success": True, "message": f"LM Studio ya está activo en {port}", "port": port}

        candidates: list[str] = []
        env_exe = os.environ.get("LM_STUDIO_EXE")
        if env_exe:
            candidates.append(env_exe)

        if os.name == "nt":
            candidates.extend(
                [
                    os.path.expandvars(r"%LOCALAPPDATA%\Programs\LM Studio\LM Studio.exe"),
                    os.path.expandvars(r"%LOCALAPPDATA%\Programs\lm-studio\LM Studio.exe"),
                    os.path.expandvars(r"C:\\Program Files\\LM Studio\\LM Studio.exe"),
                    os.path.expandvars(r"C:\\Program Files (x86)\\LM Studio\\LM Studio.exe"),
                    r"D:\\IA\\Texto\\Lmstudio\\LM Studio.exe",
                    r"D:\\IA\\Texto\\Lmstudio",
                    r"D:\\IA\\Texto\\Lmstudio\\LM Studio",
                ]
            )

        exe_path = None
        for candidate in candidates:
            if not candidate:
                continue
            if os.path.isdir(candidate):
                for name in ["LM Studio.exe", "lm studio.exe", "LMStudio.exe", "lmstudio.exe", "LM-Studio.exe"]:
                    possible = os.path.join(candidate, name)
                    if os.path.isfile(possible):
                        exe_path = possible
                        break
                if exe_path:
                    break
                try:
                    for root, _dirs, files in os.walk(candidate):
                        for fname in files:
                            if fname.lower().endswith(".exe") and "lm" in fname.lower() and "studio" in fname.lower():
                                exe_path = os.path.join(root, fname)
                                break
                        if exe_path:
                            break
                except Exception:
                    pass
                if exe_path:
                    break

            if not os.path.splitext(candidate)[1]:
                with_exe = candidate + ".exe"
                if os.path.isfile(with_exe):
                    exe_path = with_exe
                    break

            if os.path.isfile(candidate):
                exe_path = candidate
                break

        if not exe_path:
            return {
                "success": False,
                "error": "No se encontró LM Studio en rutas conocidas. Define LM_STUDIO_EXE con la ruta completa al .exe",
                "tried": candidates,
            }

        subprocess.Popen([exe_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        deadline = time.time() + 30
        while time.time() < deadline:
            if _is_port_open("127.0.0.1", port):
                return {"success": True, "message": f"LM Studio iniciado y escuchando en {port}", "port": port}
            time.sleep(1)

        return {"success": False, "error": f"LM Studio no se activó en el puerto {port} en el tiempo esperado."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _find_lms_exe() -> Optional[str]:
    """Try to locate LM Studio CLI executable (lms)."""
    env_exe = os.environ.get("LMS_EXE") or os.environ.get("LM_STUDIO_CLI")
    if env_exe and os.path.isfile(env_exe):
        return env_exe

    search_dirs = []
    for key in ("LM_STUDIO_DIR", "LM_STUDIO_HOME"):
        value = os.environ.get(key)
        if value and os.path.isdir(value):
            search_dirs.append(value)

    if os.name == "nt":
        search_dirs.extend(
            [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\LM Studio"),
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\lm-studio"),
                r"D:\\IA\\Texto\\Lmstudio",
                r"C:\\Program Files\\LM Studio",
                r"C:\\Program Files (x86)\\LM Studio",
            ]
        )

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

    return "lms"


def _lm_app_cwd(lms_path: str) -> Optional[str]:
    """Best-effort app root for LM Studio CLI commands."""
    try:
        base = os.path.dirname(lms_path)
        cur = base
        for _ in range(5):
            if os.path.isfile(os.path.join(cur, "LM Studio.exe")):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
        return base
    except Exception:
        return None


@router.post("/api/lmstudio/server/start")
def api_lmstudio_server_start(current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Start LM Studio local server via CLI: lms server start."""
    try:
        import socket
        import time

        port = lm_port()

        def _is_port_open(host: str, test_port: int, timeout: float = 0.5) -> bool:
            try:
                with socket.create_connection((host, test_port), timeout=timeout):
                    return True
            except OSError:
                return False

        if _is_port_open("127.0.0.1", port):
            return {"success": True, "message": f"Servidor ya activo en {port}", "port": port}

        lms = _find_lms_exe()
        if not lms:
            return {"success": False, "error": "No se encontró CLI de LM Studio (lms). Configura LMS_EXE o LM_STUDIO_DIR."}

        creation = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        try:
            subprocess.Popen(
                [lms, "server", "start", "--port", str(port)],
                cwd=_lm_app_cwd(lms) if os.path.isabs(lms) else None,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation,
                shell=False,
            )
        except FileNotFoundError:
            return {"success": False, "error": "No se pudo ejecutar LM Studio CLI: ejecutable no encontrado"}

        deadline = time.time() + 30
        while time.time() < deadline:
            if _is_port_open("127.0.0.1", port):
                return {"success": True, "message": f"Servidor iniciado en {port}", "port": port}
            time.sleep(1)

        return {"success": False, "error": f"El servidor no abrió el puerto {port} a tiempo"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/api/lmstudio/load")
async def api_lmstudio_load(request: Request, current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Load a model via LM Studio CLI: lms load <model>."""
    try:
        model_value: Optional[str] = None

        try:
            data = await request.json()
            if isinstance(data, str):
                model_value = data
            elif isinstance(data, dict):
                model_value = data.get("model") or next((v for k, v in data.items() if str(k).lower() == "model"), None)
        except Exception:
            pass

        if not model_value:
            try:
                form = await request.form()
                form_model = form.get("model")
                model_value = str(form_model) if form_model and not hasattr(form_model, "read") else None
            except Exception:
                pass

        if not model_value and hasattr(request, "query_params"):
            model_value = request.query_params.get("model")

        if not model_value:
            return {"success": False, "error": "Falta el parámetro 'model' en el cuerpo o la query"}

        lms = _find_lms_exe()
        if not lms:
            return {"success": False, "error": "No se encontró CLI de LM Studio (lms). Configura LMS_EXE o LM_STUDIO_DIR."}

        model_arg = model_value
        try:
            if os.path.isabs(model_arg) and os.path.exists(model_arg):
                model_arg = os.path.normpath(model_arg)
        except Exception:
            pass

        trials = [[lms, "load", model_arg], [lms, "model", "load", model_arg], [lms, "server", "load", model_arg]]

        combined_out = ""
        combined_err = ""
        app_cwd = _lm_app_cwd(lms) if os.path.isabs(lms) else None
        env = os.environ.copy()
        try:
            lms_dir = os.path.dirname(lms) if os.path.isabs(lms) else None
            if lms_dir:
                env["PATH"] = f"{lms_dir};{env.get('PATH', '')}"
        except Exception:
            pass

        for args in trials:
            try:
                completed = subprocess.run(
                    args,
                    cwd=app_cwd,
                    capture_output=True,
                    text=True,
                    timeout=180,
                    shell=False,
                    env=env,
                )
            except FileNotFoundError:
                combined_err += f"Executable not found for command: {' '.join(str(a) for a in args)}\\n"
                continue

            combined_out += f"\\n$ {' '.join(str(a) for a in args)}\\n" + (completed.stdout or "")
            combined_err += completed.stderr or ""
            if completed.returncode == 0:
                return {"success": True, "output": combined_out[-4000:]}

        return {
            "success": False,
            "output": combined_out[-4000:],
            "error": combined_err[-4000:] or "No se pudo cargar el modelo con los comandos probados",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/api/lmstudio/server/stop")
def api_lmstudio_server_stop(current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Stop LM Studio server processes (CLI) best-effort."""
    try:
        killed = []
        killed += kill_processes(["lms", "lms.exe", "lm-studio", "lm studio local server"])
        killed += kill_by_port(lm_port())
        return {"success": True, "stopped_pids": list(set(killed))}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/api/lmstudio/app/stop")
def api_lmstudio_app_stop(current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Stop LM Studio GUI app best-effort."""
    try:
        killed = kill_processes(["lm studio.exe", "lmstudio.exe"])
        return {"success": True, "stopped_pids": killed}
    except Exception as e:
        return {"success": False, "error": str(e)}


class LMStudioWarmupRequest(BaseModel):
    model: str


@router.post("/api/lmstudio/warmup")
def api_lmstudio_warmup(req: LMStudioWarmupRequest, current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Trigger tiny chat call to LM Studio API to force-load model."""
    try:
        port = lm_port()
        url = f"http://127.0.0.1:{port}/v1/chat/completions"
        payload = {
            "model": req.model,
            "messages": [{"role": "user", "content": "ok"}],
            "max_tokens": 1,
            "temperature": 0,
        }
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            return {"success": True}
        return {"success": False, "error": f"HTTP {response.status_code}", "body": response.text[-2000:]}
    except requests.Timeout:
        return {"success": False, "error": "Tiempo de espera agotado al llamar al API"}
    except Exception as e:
        return {"success": False, "error": str(e)}
