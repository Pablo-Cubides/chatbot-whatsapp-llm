"""Contacts and allowed-contacts routes extracted from admin_panel.py."""

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from crypto import decrypt_text, encrypt_text
from src.models.admin_db import get_session
from src.models.models import AllowedContact, ChatCounter, ChatProfile, Contact
from src.services.auth_system import get_current_user

router = APIRouter(tags=["contacts"])
ROOT_DIR = Path(__file__).resolve().parents[2]
ENCRYPTED_CONTEXT_PREFIX = "enc:v1:"


class ContactCreate(BaseModel):
    contact_id: str
    label: Optional[str] = None


class AllowedContactCreate(BaseModel):
    chat_id: str
    initial_context: Optional[str] = ""
    objective: Optional[str] = ""
    perfil: Optional[str] = ""


def _write_secure_context_file(path: str, content: str) -> None:
    token = encrypt_text(content or "")
    with open(path, "w", encoding="utf-8") as f:
        f.write(ENCRYPTED_CONTEXT_PREFIX + token)


def _read_secure_context_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    if raw.startswith(ENCRYPTED_CONTEXT_PREFIX):
        return decrypt_text(raw[len(ENCRYPTED_CONTEXT_PREFIX) :])
    return raw


@router.post("/api/contacts")
def api_create_contact(payload: ContactCreate, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Create a secured allowed contact record for current operator/admin."""
    session = get_session()
    try:
        enc = encrypt_text(payload.contact_id)
        owner = current_user.get("username") or current_user.get("sub") or "unknown"
        c = AllowedContact(contact_id=enc, label=payload.label, owner_user=owner)
        session.add(c)
        session.commit()
        session.refresh(c)
        return {"id": c.id, "label": c.label}
    finally:
        session.close()


@router.get("/api/contacts")
def api_list_contacts(current_user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    """List recent encrypted allowed contacts."""
    session = get_session()
    try:
        items = session.query(AllowedContact).order_by(AllowedContact.added_at.desc()).limit(200).all()
        return [{"id": i.id, "label": i.label} for i in items]
    finally:
        session.close()


@router.post("/api/allowed-contacts")
def api_create_allowed_contact(
    payload: AllowedContactCreate, current_user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    """Create or update domain contact/profile and optional encrypted context files."""
    session = get_session()
    try:
        contact = session.query(Contact).filter(Contact.chat_id == payload.chat_id).first()
        if not contact:
            contact = Contact(chat_id=payload.chat_id, auto_enabled=True)
            session.add(contact)

        profile = session.query(ChatProfile).filter(ChatProfile.chat_id == payload.chat_id).first()
        if not profile:
            profile = ChatProfile()
            profile.chat_id = payload.chat_id
            profile.initial_context = payload.initial_context
            profile.objective = payload.objective
            profile.is_ready = True
            session.add(profile)
        else:
            profile.initial_context = payload.initial_context
            profile.objective = payload.objective
            profile.is_ready = True

        session.commit()

        try:
            chat_dir = ROOT_DIR / "contextos" / f"chat_{payload.chat_id}"
            chat_dir.mkdir(parents=True, exist_ok=True)
            if (payload.perfil or "").strip():
                _write_secure_context_file(str(chat_dir / "perfil.txt"), payload.perfil or "")
            if (payload.initial_context or "").strip():
                _write_secure_context_file(str(chat_dir / "contexto.txt"), payload.initial_context or "")
            if (payload.objective or "").strip():
                _write_secure_context_file(str(chat_dir / "objetivo.txt"), payload.objective or "")
        except Exception:
            pass

        return {"success": True, "chat_id": payload.chat_id, "message": f"Contact {payload.chat_id} added successfully"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/api/allowed-contacts")
def api_list_allowed_contacts(current_user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Return active contacts with profile readiness and encrypted profile flags."""
    session = get_session()
    try:
        results = (
            session.query(Contact, ChatProfile)
            .outerjoin(ChatProfile, Contact.chat_id == ChatProfile.chat_id)
            .filter(Contact.auto_enabled)
            .all()
        )

        contacts = []
        for contact, profile in results:
            perfil_path = ROOT_DIR / "contextos" / f"chat_{contact.chat_id}" / "perfil.txt"
            has_perfil = False
            if perfil_path.exists():
                try:
                    has_perfil = bool(_read_secure_context_file(str(perfil_path)).strip())
                except Exception:
                    has_perfil = True

            contacts.append(
                {
                    "chat_id": contact.chat_id,
                    "name": contact.name or contact.chat_id,
                    "initial_context": profile.initial_context if profile else "",
                    "objective": profile.objective if profile else "",
                    "perfil": has_perfil,
                    "is_ready": profile.is_ready if profile else False,
                    "created_at": contact.created_at.isoformat() if contact.created_at else None,
                }
            )

        return contacts
    finally:
        session.close()


@router.delete("/api/allowed-contacts/{chat_id}")
def api_remove_allowed_contact(chat_id: str, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Remove contact/profile/counter data for a chat."""
    session = get_session()
    try:
        contact = session.query(Contact).filter(Contact.chat_id == chat_id).first()
        if contact:
            session.delete(contact)

        profile = session.query(ChatProfile).filter(ChatProfile.chat_id == chat_id).first()
        if profile:
            session.delete(profile)

        counter = session.query(ChatCounter).filter(ChatCounter.chat_id == chat_id).first()
        if counter:
            session.delete(counter)

        session.commit()
        return {"success": True, "message": f"Contact {chat_id} removed successfully"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
