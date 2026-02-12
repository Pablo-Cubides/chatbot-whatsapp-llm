"""
🧠 Reasoner - Sistema de Análisis Estratégico de Conversaciones
Genera estrategias de conversación orientadas a objetivos usando LLM
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from openai import OpenAI

from chat_sessions import (
    activate_new_strategy,
    get_active_strategy,
    get_profile,
    load_last_context,
)

# Configure logger
logger = logging.getLogger(__name__)

HERE = os.path.dirname(__file__)
REASONER_PAYLOAD_PATH = os.environ.get("REASONER_PAYLOAD_PATH", os.path.join(HERE, "payload_reasoner.json"))

# Initialize LM Studio client - lazy initialization
_client = None


def get_lm_studio_client() -> Optional[OpenAI]:
    """Get or create LM Studio client with lazy initialization."""
    global _client
    if _client is None:
        try:
            _client = OpenAI(
                base_url=os.environ.get("LM_STUDIO_URL", "http://127.0.0.1:1234/v1"),
                api_key=os.environ.get("LM_STUDIO_API_KEY", "lm-studio"),
            )
        except Exception as e:
            logger.error(f"Error inicializando cliente LM Studio: {e}")
            _client = None
    return _client


def _load_payload() -> dict[str, Any]:
    """Load reasoner payload template from JSON file."""
    with open(REASONER_PAYLOAD_PATH, encoding="utf-8") as f:
        return json.load(f)


def _build_reasoner_messages(chat_id: str, turns: int = 30) -> tuple[list[dict[str, str]], str]:
    """
    Build messages for the reasoner based on chat context.

    Args:
        chat_id: Chat identifier
        turns: Number of recent turns to include

    Returns:
        Tuple of (messages list, snapshot string)
    """
    profile = get_profile(chat_id)
    active = get_active_strategy(chat_id)
    history = load_last_context(chat_id) or []
    history_tail = history[-turns:]

    messages: list[dict[str, str]] = []

    # System messages with context
    if profile:
        if (profile.objective or "").strip():
            messages.append({"role": "system", "content": f"Objetivo del chat: {profile.objective}"})
        if (profile.instructions or "").strip():
            messages.append({"role": "system", "content": f"Instrucciones del perfil: {profile.instructions}"})
    if active and (active.strategy_text or "").strip():
        messages.append(
            {"role": "system", "content": f"Estrategia vigente (versión {active.version}):\n{active.strategy_text}"}
        )

    # Provide a compact snapshot of recent dialog for analysis
    snapshot_lines: list[str] = []
    for m in history_tail:
        role = m.get("role", "user")
        content = m.get("content", "")
        snapshot_lines.append(f"{role}: {content}")
    snapshot = "\n".join(snapshot_lines)

    messages.append(
        {
            "role": "user",
            "content": (
                "Analiza el siguiente snapshot de la conversación reciente y el objetivo dado. "
                "Propón una estrategia concreta para los próximos 10 mensajes del respondedor.\n\n"
                f"SNAPSHOT (reciente):\n{snapshot}"
            ),
        }
    )

    return messages, snapshot


def run_reasoner_for_chat(chat_id: str) -> Optional[int]:
    """
    Run the analysis model to produce a new strategy and activate it.

    Args:
        chat_id: Chat identifier

    Returns:
        New strategy version number, or None on failure
    """
    payload = _load_payload()
    payload = payload.copy()
    payload["messages"] = list(payload.get("messages", []))
    messages, snapshot = _build_reasoner_messages(chat_id)
    payload["messages"].extend(messages)

    client = get_lm_studio_client()
    if client is None:
        logger.error("LM Studio cliente no disponible para run_reasoner_for_chat")
        return None

    try:
        resp = client.chat.completions.create(**payload)
        strategy_text = resp.choices[0].message.content
    except Exception as e:
        logger.error(f"Error llamando a LM Studio: {e}")
        return None

    # Save as new active strategy (with snapshot stored for audit)
    version = activate_new_strategy(chat_id, strategy_text=strategy_text, source_snapshot=snapshot)
    return version


def update_chat_context_and_profile(chat_id: str) -> Optional[dict[str, Any]]:
    """
    Runs the reasoner to produce:
    - contexto_prioritario: brief summary of the most important ongoing items
    - estrategia: operational strategy text for next turns
    - perfil_update: new/updated profile notes (gustos, metas, etc.)

    Persists results to:
    - Files under contextos/chat_{chat_id}/perfil.txt and contexto.txt
    - DB ChatProfile.initial_context (mirrors contexto prioritario)
    - DB ChatStrategy (activate new strategy version)

    Returns a dict with details: {version, wrote_contexto, wrote_perfil}
    """
    # 1) Build a structured prompt
    payload = _load_payload()
    payload = payload.copy()
    payload["messages"] = list(payload.get("messages", []))

    profile = get_profile(chat_id)
    active = get_active_strategy(chat_id)
    history = load_last_context(chat_id) or []
    tail = history[-30:]

    perfil_text_parts = []
    if profile:
        if (profile.initial_context or "").strip():
            perfil_text_parts.append(f"Contexto inicial: {profile.initial_context}")
        if (profile.objective or "").strip():
            perfil_text_parts.append(f"Objetivo: {profile.objective}")
        if (profile.instructions or "").strip():
            perfil_text_parts.append(f"Instrucciones: {profile.instructions}")
    perfil_text = "\n".join(perfil_text_parts) or "(sin perfil)"

    estrategia_prev = active.strategy_text if active and (active.strategy_text or "").strip() else "(sin estrategia previa)"

    snapshot_lines = []
    for m in tail:
        role = m.get("role", "user")
        content = m.get("content", "")
        snapshot_lines.append(f"{role}: {content}")
    snapshot = "\n".join(snapshot_lines)

    instructions = (
        "Eres un analista. NO hables con el usuario. Devuelve SOLO JSON válido con las claves: "
        "perfil_update, contexto_prioritario, estrategia.\n"
        "- perfil_update: texto conciso con hechos duraderos sobre gustos/metas/datos del usuario relevantes al objetivo.\n"
        "- contexto_prioritario: resumen corto de lo más importante que se viene hablando (estado actual).\n"
        "- estrategia: plan operativo concreto para los próximos 10 mensajes del bot.\n"
        "No uses markdown. No incluyas comentarios fuera del JSON."
    )

    payload["messages"].extend(
        [
            {"role": "system", "content": instructions},
            {"role": "user", "content": f"Perfil actual del chat:\n{perfil_text}"},
            {"role": "user", "content": f"Estrategia vigente:\n{estrategia_prev}"},
            {"role": "user", "content": f"Snapshot reciente:\n{snapshot}"},
        ]
    )

    # 2) Call model
    client = get_lm_studio_client()
    if client is None:
        logger.error("LM Studio cliente no disponible para update_chat_context_and_profile")
        return None

    try:
        resp = client.chat.completions.create(**payload)
        txt = resp.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"Error llamando a LM Studio: {e}")
        return None

    # 3) Parse JSON
    data: dict[str, str] = {"perfil_update": "", "contexto_prioritario": "", "estrategia": ""}
    try:
        data.update(json.loads(txt))
    except (json.JSONDecodeError, ValueError):
        # Fallback: attempt naive section extraction
        import re

        for label in ["perfil_update", "contexto_prioritario", "estrategia"]:
            m = re.search(rf'"{label}"\s*:\s*"([^"]*)"', txt)
            if m:
                data[label] = m.group(1).strip()

    contexto_prioritario = (data.get("contexto_prioritario") or "").strip()
    estrategia_text = (data.get("estrategia") or "").strip()
    perfil_update = (data.get("perfil_update") or "").strip()

    # 4) Persist files
    chat_dir = os.path.join(HERE, "contextos", f"chat_{chat_id}")
    os.makedirs(chat_dir, exist_ok=True)
    wrote_contexto = False
    wrote_perfil = False

    # contexto: priorizado + estrategia
    try:
        contexto_path = os.path.join(chat_dir, "contexto.txt")
        blocks = []
        if contexto_prioritario:
            blocks.append("CONTEXTO PRIORITARIO:\n" + contexto_prioritario)
        if estrategia_text:
            blocks.append("ESTRATEGIA:\n" + estrategia_text)
        if blocks:
            with open(contexto_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(blocks))
            wrote_contexto = True
    except Exception as e:
        logger.error(f"Error escribiendo contexto para {chat_id}: {e}")

    # perfil: append update with timestamp
    try:
        if perfil_update:
            perfil_path = os.path.join(chat_dir, "perfil.txt")
            existing = ""
            if os.path.exists(perfil_path):
                with open(perfil_path, encoding="utf-8") as f:
                    existing = f.read()
            stamp = datetime.now(timezone.utc).isoformat()
            appended = (existing + ("\n\n" if existing else "") + f"[Actualización {stamp}]\n" + perfil_update).strip()
            with open(perfil_path, "w", encoding="utf-8") as f:
                f.write(appended)
            wrote_perfil = True
    except Exception as e:
        logger.error(f"Error escribiendo perfil para {chat_id}: {e}")

    # 5) Persist to DB
    version = activate_new_strategy(chat_id, strategy_text=estrategia_text or estrategia_prev, source_snapshot=snapshot)

    # Mirror contexto prioritario into ChatProfile.initial_context for faster access
    try:
        from admin_db import get_session as _gs

        from models import ChatProfile as _CP

        sess = _gs()
        try:
            prof = sess.get(_CP, chat_id) or _CP(chat_id=chat_id)
            prof.initial_context = contexto_prioritario or prof.initial_context or ""
            prof.is_ready = True
            prof.updated_at = datetime.now(timezone.utc)
            sess.add(prof)
            sess.commit()
        except Exception as e:
            sess.rollback()
            logger.error(f"Error actualizando perfil DB para {chat_id}: {e}")
        finally:
            sess.close()
    except ImportError as e:
        logger.warning(f"No se pudo importar admin_db/models: {e}")

    return {
        "version": version,
        "wrote_contexto": wrote_contexto,
        "wrote_perfil": wrote_perfil,
    }
