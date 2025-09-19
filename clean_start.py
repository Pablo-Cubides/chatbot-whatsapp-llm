#!/usr/bin/env python3
"""
Entrypoint robusto para iniciar el backend y frontend juntos.

Este script:
- Maneja SIGINT/SIGTERM y termina los procesos hijos limpiamente.
- Inicia primero el backend, espera por un endpoint de health antes de iniciar el frontend.
- Sirve el `build` del frontend con un servidor estático (o inicia `npm run dev` si se solicita mediante env VAR).
"""

from pathlib import Path
import os
import sys
import time
import signal
import subprocess
import webbrowser

try:
    import requests
except Exception:
    requests = None


LOG_PREFIX = "[clean_start]"


def log(msg: str):
    print(f"{LOG_PREFIX} {msg}", flush=True)


children = []


def terminate_children(signum=None, frame=None):
    log("Received stop signal, terminating children...")
    for p in list(children):
        try:
            if p.poll() is None:
                log(f"Terminating PID {p.pid}")
                try:
                    if os.name != "nt":
                        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                    else:
                        p.terminate()
                except Exception as e:
                    log(f"Error terminating process group: {e}")
                    p.terminate()
        except Exception as e:
            log(f"Error while terminating children: {e}")
    # wait a moment
    time.sleep(2)
    for p in list(children):
        try:
            if p.poll() is None:
                p.kill()
        except Exception as e:
            log(f"Error killing child: {e}")
    log("All children terminated")
    sys.exit(0)


def wait_for_url(url: str, timeout: int = 30) -> bool:
    if requests is None:
        # no requests available; fallback to sleep
        log("requests not installed; skipping health-check wait (sleep fallback)")
        time.sleep(3)
        return True
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def start_backend(backend_dir: Path, python_exe: str = sys.executable) -> subprocess.Popen:
    log("Starting backend (uvicorn fixed_server:app on 8014)")
    cmd = [python_exe, "-m", "uvicorn", "fixed_server:app", "--host", "0.0.0.0", "--port", "8014", "--log-level", "info"]
    p = subprocess.Popen(cmd, cwd=str(backend_dir), start_new_session=True)
    children.append(p)
    return p


def start_frontend_static(build_dir: Path) -> subprocess.Popen:
    log(f"Serving frontend static from {build_dir} on port 3000")
    cmd = [sys.executable, "-m", "http.server", "3000", "--bind", "0.0.0.0"]
    p = subprocess.Popen(cmd, cwd=str(build_dir), start_new_session=True)
    children.append(p)
    return p


def start_frontend_dev(frontend_dir: Path) -> subprocess.Popen:
    log("Starting frontend in dev mode (npm run dev)")
    npm = "npm.cmd" if os.name == "nt" else "npm"
    cmd = [npm, "run", "dev"]
    p = subprocess.Popen(cmd, cwd=str(frontend_dir), start_new_session=True)
    children.append(p)
    return p


def main():
    signal.signal(signal.SIGINT, terminate_children)
    signal.signal(signal.SIGTERM, terminate_children)

    root = Path(__file__).parent
    backend_dir = root
    frontend_dir = root.parent / "Frontend"

    log("Starting clean start sequence")

    start_backend(backend_dir)

    backend_ready = wait_for_url("http://127.0.0.1:8014/api/status", timeout=30)
    if not backend_ready:
        log("Warning: backend did not respond within timeout; check logs")
    else:
        log("Backend ready")

    use_dev = os.getenv("USE_DEV_FRONTEND", "0") == "1"
    if use_dev:
        start_frontend_dev(frontend_dir)
    else:
        build_dir = frontend_dir / "build"
        if build_dir.exists():
            start_frontend_static(build_dir)
        else:
            log("Frontend build not found; falling back to dev server")
            start_frontend_dev(frontend_dir)

    if os.getenv("OPEN_BROWSER", "1") == "1":
        try:
            webbrowser.open("http://localhost:3000")
        except Exception:
            pass

    log("System startup complete — monitoring child processes")
    try:
        while True:
            time.sleep(1)
            for p in list(children):
                if p.poll() is not None:
                    log(f"Process {p.pid} exited with {p.returncode}")
                    children.remove(p)
    except KeyboardInterrupt:
        terminate_children()


if __name__ == "__main__":
    main()