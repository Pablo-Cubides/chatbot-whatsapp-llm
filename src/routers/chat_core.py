"""Core chat/settings/prompts/status routes extracted from admin_panel.py."""

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, Optional

import chat_sessions
import stub_chat
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.services.adaptive_layer import adaptive_layer_manager
from src.services.auth_system import get_current_user, require_admin
from src.services.business_config_manager import business_config
from src.services.queue_system import queue_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat-core"])


class ScheduleIn(BaseModel):
    chat_id: str
    message: str
    when: Optional[str] = None  # ISO timestamp or 'now'


@router.post("/api/schedule")
def api_schedule(payload: ScheduleIn, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, bool]:
    """Schedule a future outbound message entry for a chat."""
    when_dt = None
    when_raw = (payload.when or "now").strip().lower()
    if when_raw != "now":
        parsed = datetime.fromisoformat((payload.when or "").replace("Z", "+00:00"))
        when_dt = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    queue_manager.enqueue_message(
        chat_id=payload.chat_id,
        message=payload.message,
        when=when_dt,
        priority=1,
        metadata={"source": "api_schedule", "requested_by": current_user.get("username", "unknown")},
    )
    return {"ok": True}


async def event_stream() -> AsyncIterator[str]:
    import time

    sfile = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "status.json")
    while True:
        payload = {"time": time.time()}
        if os.path.exists(sfile):
            try:
                with open(sfile, encoding="utf-8") as f:
                    payload.update(json.load(f))
            except Exception:
                pass
        yield f"data: {json.dumps(payload)}\n\n"
        await asyncio.sleep(1)


@router.get("/api/events")
async def api_events(current_user: dict[str, Any] = Depends(get_current_user)) -> StreamingResponse:
    """Return an SSE stream with periodic runtime status payloads."""
    return StreamingResponse(event_stream(), media_type="text/event-stream")


class ClearChatIn(BaseModel):
    chat_id: str


@router.post("/api/conversations/clear", response_class=JSONResponse)
def api_clear_conversation(
    payload: ClearChatIn, current_user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    """Delete persisted conversation history for one chat."""
    try:
        n = chat_sessions.clear_conversation_history(payload.chat_id)
        return {"success": True, "deleted": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/conversations/clear-all", response_class=JSONResponse)
def api_clear_all_conversations(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Delete persisted conversation history for all chats."""
    try:
        n = chat_sessions.clear_all_conversation_histories()
        return {"success": True, "deleted": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ChatIn(BaseModel):
    chat_id: str
    message: str


@router.post("/api/chat")
async def api_chat(payload: ChatIn, current_user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Generate chat response and persist user/assistant context."""
    try:
        history = chat_sessions.load_last_context(payload.chat_id) or []
        adaptive_overrides: dict[str, Any] = {}

        try:
            adaptive_layer_manager.business_config = business_config
            adaptive_layer_manager.sync_runtime_settings()
            adaptive_layer_manager.register_interaction(payload.chat_id)
            adaptive_overrides = adaptive_layer_manager.get_runtime_overrides(payload.chat_id)
            adaptive_layer_manager.apply_runtime_overrides(adaptive_overrides, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        except Exception as adaptive_error:
            logger.warning(f"Adaptive override warning: {adaptive_error}")

        user_message = payload.message
        style_hint = adaptive_overrides.get("style") if adaptive_overrides else None
        if style_hint == "concise":
            user_message = f"[Estilo: respuesta breve, directa y profesional]\n{payload.message}"
        elif style_hint == "empathetic":
            user_message = f"[Estilo: tono empático, cálido y conversacional]\n{payload.message}"

        reply = stub_chat.chat(user_message, payload.chat_id, history)
        history.append({"role": "user", "content": payload.message})
        history.append({"role": "assistant", "content": reply})
        chat_sessions.save_context(payload.chat_id, history)

        try:
            adaptive_layer_manager.business_config = business_config
            adaptive_layer_manager.sync_runtime_settings()

            if adaptive_layer_manager.should_run_now():
                batch = chat_sessions.load_recent_conversations(limit=adaptive_layer_manager.default_batch_limit)
                await adaptive_layer_manager.run_adaptive_cycle(conversations=batch)
        except Exception as adaptive_error:
            logger.warning(f"Adaptive layer warning: {adaptive_error}")

        return JSONResponse({"reply": reply})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


class ChatTestIn(BaseModel):
    message: str
    chat_id: Optional[str] = "test_chat"


@router.post("/api/chat/test")
def api_chat_test(payload: ChatTestIn, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Run a deterministic chat test call against the stub provider."""
    reply = stub_chat.chat(payload.message, payload.chat_id or "test_chat", [])
    return {"success": True, "response": reply}


@router.get("/api/status")
def api_status(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Expose combined runtime status for settings and prompts."""
    sfile = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "settings.json")
    pfile = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "prompts.json")

    settings = {"temperature": 0.7, "max_tokens": 512, "reason_after_messages": 10, "chat_enabled": True}
    if os.path.exists(sfile):
        try:
            with open(sfile, encoding="utf-8") as f:
                settings.update(json.load(f))
        except Exception:
            pass

    prompts = {
        "conversational": "Responde de forma útil y breve.",
        "reasoner": "Piensa paso a paso antes de responder.",
        "conversation": "",
    }
    if os.path.exists(pfile):
        try:
            with open(pfile, encoding="utf-8") as f:
                prompts.update(json.load(f))
        except Exception:
            pass

    return {
        "status": "ok",
        "app": "admin-panel",
        "chat_enabled": settings.get("chat_enabled", True),
        "settings": {
            "temperature": settings.get("temperature", 0.7),
            "max_tokens": settings.get("max_tokens", 512),
            "reason_after_messages": settings.get("reason_after_messages", 10),
        },
        "prompts": prompts,
    }


class PromptsIn(BaseModel):
    conversational: Optional[str] = None
    reasoner: Optional[str] = None
    conversation: Optional[str] = None


@router.put("/api/prompts")
def api_update_prompts(payload: PromptsIn, current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, bool]:
    """Update prompt templates used by chat and reasoning layers."""
    pfile = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "prompts.json")
    data = {}
    if os.path.exists(pfile):
        try:
            with open(pfile, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    if payload.conversational is not None:
        data["conversational"] = payload.conversational
    if payload.reasoner is not None:
        data["reasoner"] = payload.reasoner
    if payload.conversation is not None:
        data["conversation"] = payload.conversation
    os.makedirs(os.path.dirname(pfile), exist_ok=True)
    with open(pfile, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"ok": True}


@router.get("/api/prompts")
def api_get_prompts(current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, str]:
    """Read persisted prompt templates or return defaults."""
    pfile = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "prompts.json")
    if os.path.exists(pfile):
        with open(pfile, encoding="utf-8") as f:
            return json.load(f)
    return {"conversational": "", "reasoner": "", "conversation": ""}


class SettingsIn(BaseModel):
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    reason_after_messages: Optional[int] = None
    respond_to_all: Optional[bool] = None


@router.put("/api/settings")
def api_update_settings(payload: SettingsIn, current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, bool]:
    """Persist runtime settings used by chat generation."""
    sfile = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "settings.json")
    settings = {}
    if os.path.exists(sfile):
        try:
            with open(sfile, encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            settings = {}
    if payload.temperature is not None:
        settings["temperature"] = payload.temperature
    if payload.max_tokens is not None:
        settings["max_tokens"] = payload.max_tokens
    if payload.reason_after_messages is not None:
        settings["reason_after_messages"] = payload.reason_after_messages
    if payload.respond_to_all is not None:
        settings["respond_to_all"] = payload.respond_to_all
    os.makedirs(os.path.dirname(sfile), exist_ok=True)
    with open(sfile, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    return {"ok": True}


@router.get("/api/settings")
def api_get_settings(current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Return persisted runtime settings or safe defaults."""
    sfile = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "settings.json")
    if os.path.exists(sfile):
        with open(sfile, encoding="utf-8") as f:
            return json.load(f)
    return {"temperature": 0.7, "max_tokens": 512, "reason_after_messages": 10, "respond_to_all": False}
