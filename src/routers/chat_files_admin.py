"""Chat context + editable files admin routes extracted from admin_panel."""

import json
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from crypto import decrypt_text, encrypt_text
from reasoner import update_chat_context_and_profile
from src.models.admin_db import get_session
from src.models.models import ChatProfile
from src.services.auth_system import get_current_user

router = APIRouter(tags=["chat-files-admin"])

ENCRYPTED_CONTEXT_PREFIX = "enc:v1:"

try:
    import psutil
except ImportError:
    psutil = None


def _read_secure_context_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    if raw.startswith(ENCRYPTED_CONTEXT_PREFIX):
        return decrypt_text(raw[len(ENCRYPTED_CONTEXT_PREFIX) :])
    return raw


def _write_secure_context_file(path: str, content: str) -> None:
    token = encrypt_text(content or "")
    with open(path, "w", encoding="utf-8") as f:
        f.write(ENCRYPTED_CONTEXT_PREFIX + token)


def _script_match_in_cmdline(proc, script_name: str) -> bool:
    cmdline = proc.info.get("cmdline") or []
    if isinstance(cmdline, str):
        cmd = cmdline.lower()
    else:
        cmd = " ".join(str(part) for part in cmdline).lower()
    return script_name.lower() in cmd


def _get_playwright_profile_dir() -> str:
    try:
        cfg_path = Path(__file__).resolve().parents[2] / "config" / "playwright_config.json"
        if cfg_path.exists():
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            profile = cfg.get("profile_dir")
            if isinstance(profile, str) and profile.strip():
                p = profile.strip()
                if not os.path.isabs(p):
                    p = str((cfg_path.parent.parent / p).resolve())
                return p
    except Exception:
        pass
    return str((Path(__file__).resolve().parents[2] / "data" / "whatsapp-profile").resolve())


class FileContent(BaseModel):
    content: str


class ChatContextUpdate(BaseModel):
    perfil: Optional[str] = None
    contexto: Optional[str] = None
    objetivo: Optional[str] = None


@router.get("/api/files/{filename}")
def api_get_file(filename: str, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Get content of a file (docs, perfil, ultimo_contexto, etc.)."""
    try:
        allowed_files = {
            "ejemplo_chat": "Docs/ejemplo_chat.txt",
            "perfil": "Docs/Perfil.txt",
            "ultimo_contexto": "Docs/Ultimo_contexto.txt",
        }

        if filename not in allowed_files:
            raise HTTPException(status_code=404, detail="File not found")

        app_root = Path(__file__).resolve().parents[2]
        file_path = app_root / allowed_files[filename]

        if not file_path.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("", encoding="utf-8")

        content = ""
        for encoding in ["utf-8", "latin-1", "cp1252"]:
            try:
                content = file_path.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue

        return {"filename": filename, "content": content, "path": str(file_path)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/files/{filename}")
def api_update_file(filename: str, file_content: FileContent, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Update content of a file."""
    try:
        allowed_files = {
            "ejemplo_chat": "Docs/ejemplo_chat.txt",
            "perfil": "Docs/Perfil.txt",
            "ultimo_contexto": "Docs/Ultimo_contexto.txt",
        }

        if filename not in allowed_files:
            raise HTTPException(status_code=404, detail="File not found")

        app_root = Path(__file__).resolve().parents[2]
        file_path = app_root / allowed_files[filename]
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(file_content.content, encoding="utf-8")

        return {"success": True, "filename": filename, "message": "File updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/chats")
def api_get_chats(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, list[str]]:
    """Get list of chat contexts."""
    try:
        app_root = Path(__file__).resolve().parents[2]
        contextos_dir = app_root / "contextos"
        contextos_dir.mkdir(parents=True, exist_ok=True)

        chats = []
        for path in contextos_dir.iterdir():
            if path.is_dir() and path.name.startswith("chat_"):
                chats.append(path.name[len("chat_") :])

        return {"chats": sorted(chats)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/chats/{chat_id}")
def api_get_chat_context(chat_id: str, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Get context for a specific chat."""
    try:
        app_root = Path(__file__).resolve().parents[2]
        chat_id = "".join(c for c in chat_id if c.isalnum() or c in "_-")
        chat_dir = app_root / "contextos" / f"chat_{chat_id}"
        chat_dir.mkdir(parents=True, exist_ok=True)

        result = {
            "chat_id": chat_id,
            "files": {"perfil": "", "contexto": "", "objetivo": "", "historial": []},
            "automator_pid": None,
            "browser_pids": [],
        }

        perfil_path = chat_dir / "perfil.txt"
        contexto_path = chat_dir / "contexto.txt"
        objetivo_path = chat_dir / "objetivo.txt"

        if perfil_path.exists():
            try:
                result["files"]["perfil"] = _read_secure_context_file(str(perfil_path))
            except Exception:
                result["files"]["perfil"] = ""
        if contexto_path.exists():
            try:
                result["files"]["contexto"] = _read_secure_context_file(str(contexto_path))
            except Exception:
                result["files"]["contexto"] = ""
        if objetivo_path.exists():
            try:
                result["files"]["objetivo"] = _read_secure_context_file(str(objetivo_path))
            except Exception:
                result["files"]["objetivo"] = ""

        if psutil is not None:
            try:
                for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                    try:
                        if _script_match_in_cmdline(proc, "whatsapp_automator.py"):
                            result["automator_pid"] = proc.info.get("pid")
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception:
                pass

        try:
            profile = _get_playwright_profile_dir()
            prof_norm = profile.lower().replace("\\", "/").strip() if profile else ""
            if prof_norm and psutil is not None:
                targets = ["chrome.exe", "msedge.exe", "chromium.exe", "chrome", "msedge", "chromium"]
                for p in psutil.process_iter(["pid", "name", "cmdline"]):
                    try:
                        name = (p.info.get("name") or "").lower()
                        cmd = " ".join(p.info.get("cmdline") or []).lower().replace("\\", "/")
                        if any(t in name for t in targets) and prof_norm in cmd:
                            result["browser_pids"].append(p.info.get("pid"))
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
        except Exception:
            pass

        historial_path = chat_dir / "historial.json"
        try:
            if historial_path.exists():
                with open(historial_path, encoding="utf-8") as f:
                    result["files"]["historial"] = json.load(f)
        except Exception:
            result["files"]["historial"] = []

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/chats/{chat_id}")
def api_update_chat_context(
    chat_id: str,
    update: ChatContextUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Update context for a specific chat."""
    try:
        app_root = Path(__file__).resolve().parents[2]
        chat_id = "".join(c for c in chat_id if c.isalnum() or c in "_-")

        chat_dir = app_root / "contextos" / f"chat_{chat_id}"
        chat_dir.mkdir(parents=True, exist_ok=True)

        updated_files = []

        if update.perfil is not None:
            _write_secure_context_file(str(chat_dir / "perfil.txt"), update.perfil)
            updated_files.append("perfil.txt")

        if update.contexto is not None:
            _write_secure_context_file(str(chat_dir / "contexto.txt"), update.contexto)
            updated_files.append("contexto.txt")
        if update.objetivo is not None:
            _write_secure_context_file(str(chat_dir / "objetivo.txt"), update.objetivo)
            updated_files.append("objetivo.txt")

        try:
            session = get_session()
            profile = session.query(ChatProfile).filter(ChatProfile.chat_id == chat_id).first()
            if not profile:
                profile = ChatProfile()
                profile.chat_id = chat_id
                session.add(profile)
            if update.contexto is not None:
                profile.initial_context = update.contexto
            if update.objetivo is not None:
                profile.objective = update.objetivo
            session.commit()
            session.close()
        except Exception:
            pass

        return {"success": True, "chat_id": chat_id, "updated_files": updated_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/chats/{chat_id}/refresh-context")
def api_refresh_chat_context(chat_id: str, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Execute reasoner to refresh chat profile/context files."""
    try:
        chat_id = "".join(c for c in chat_id if c.isalnum() or c in "_-")
        result = update_chat_context_and_profile(chat_id)
        return {"success": True, "chat_id": chat_id, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
