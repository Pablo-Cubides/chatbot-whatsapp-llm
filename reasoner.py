import json
import os
import logging
from datetime import datetime
from openai import OpenAI

from admin_db import get_session
from models import Conversation
import chat_sessions as cs

# Configure logger
logger = logging.getLogger(__name__)

HERE = os.path.dirname(__file__)
REASONER_PAYLOAD_PATH = os.environ.get("REASONER_PAYLOAD_PATH", os.path.join(HERE, "payload_reasoner.json"))

# LM Studio client
client = OpenAI(
    base_url=os.environ.get("LM_STUDIO_URL", "http://127.0.0.1:1234/v1"), 
    api_key=os.environ.get("LM_STUDIO_API_KEY", "lm-studio")
)


def _load_payload_template():
    with open(REASONER_PAYLOAD_PATH, encoding="utf-8") as f:
        return json.load(f)


def _last_turns(chat_id: str, n_turns: int = 30) -> str:
    """Fetch last N messages from history (flatten user/assistant texts)."""
    session = get_session()
    rows = (
        session.query(Conversation)
        .filter(Conversation.chat_id == chat_id)
        .order_by(Conversation.timestamp.desc())
        .limit(10)  # last 10 saved contexts; each is a list of turns
        .all()
    )
    session.close()
    texts = []
    for row in reversed(rows):
        try:
            import json as _json
            from crypto import decrypt_text
            ctx = _json.loads(decrypt_text(row.context))
            for m in ctx[-n_turns:]:
                role = m.get("role")
                content = m.get("content")
                if role and content:
                    texts.append(f"{role}: {content}")
        except Exception:
            continue
    return "\n".join(texts[-(n_turns*2):])


def run_reasoner_for_chat(chat_id: str) -> int:
    """Run the analysis model to produce a new strategy and activate it.
    Returns the new strategy version number.
    
    ENHANCED: Now prominently uses contact objectives to generate
    targeted strategies that actively pursue the defined goal.
    """
    profile = cs.get_profile(chat_id)
    prev = cs.get_active_strategy(chat_id)

    # Build prompt pieces - OBJECTIVE IS NOW PRIORITY
    objective = ""
    if profile and (profile.objective or '').strip():
        objective = profile.objective
    
    profile_block = []
    if profile and (profile.initial_context or '').strip():
        profile_block.append(f"Contexto inicial: {profile.initial_context}")
    if profile and (profile.instructions or '').strip():
        profile_block.append(f"Instrucciones específicas: {profile.instructions}")
    profile_text = "\n".join(profile_block) or "(sin perfil adicional)"

    prev_text = prev.strategy_text if prev and (prev.strategy_text or '').strip() else "(sin estrategia previa)"
    convo_snapshot = _last_turns(chat_id, n_turns=40)

    # Build payload with OBJECTIVE-FOCUSED prompt
    payload = _load_payload_template()
    messages = list(payload.get("messages", []))
    
    # Enhanced system message that prioritizes objective
    system_message = """Eres un estratega de conversaciones. NO hables con el usuario final.
Tu tarea es producir una ESTRATEGIA OPERATIVA para el bot respondedor.

REGLAS CRÍTICAS:
1. El OBJETIVO del contacto es la PRIORIDAD ABSOLUTA
2. Cada mensaje del bot debe acercar la conversación hacia el objetivo
3. Identifica el PROGRESO actual hacia el objetivo (0-100%)
4. Propón TÁCTICAS CONCRETAS para los próximos 10 mensajes
5. Incluye indicadores de éxito y puntos de cierre

FORMATO DE RESPUESTA:
- Análisis de progreso actual (%)
- Obstáculos identificados
- Estrategia para próximos 10 mensajes
- Tácticas de cierre o conversión"""
    
    messages += [{"role": "system", "content": system_message}]
    
    # Add objective prominently if exists
    if objective:
        messages.append({
            "role": "user", 
            "content": f"🎯 OBJETIVO PRIORITARIO CON ESTE CLIENTE:\n{objective}\n\nTODA la estrategia debe orientarse a lograr este objetivo."
        })
    else:
        messages.append({
            "role": "user", 
            "content": "⚠️ No hay objetivo definido. Genera una estrategia genérica de engagement y calificación."
        })
    
    if profile_text != "(sin perfil adicional)":
        messages.append({"role": "user", "content": f"Perfil del cliente:\n{profile_text}"})
    
    messages.append({"role": "user", "content": f"Estrategia vigente:\n{prev_text}"})
    messages.append({"role": "user", "content": f"Extracto de conversación (últimos turnos):\n{convo_snapshot}"})
    messages.append({
        "role": "user", 
        "content": "Genera la ESTRATEGIA OPERATIVA enfocada en el objetivo. Incluye análisis de progreso y tácticas concretas."
    })
    payload["messages"] = messages

    # Call LM Studio
    client = get_lm_studio_client()
    if client is None:
        logger.error("LM Studio cliente no disponible")
        return
    
    resp = client.chat.completions.create(**payload)
    text = resp.choices[0].message.content

    # Save as new strategy and activate
    source_snapshot = json.dumps({
        "profile": profile_text,
        "prev_strategy": prev_text,
        "excerpt": convo_snapshot[:4000],
        "at": datetime.utcnow().isoformat()
    }, ensure_ascii=False)

    ver = cs.activate_new_strategy(chat_id, strategy_text=text, source_snapshot=source_snapshot)
    return ver
import os
import json
from datetime import datetime
from typing import List, Dict, Any

from openai import OpenAI

from chat_sessions import (
    get_profile,
    get_active_strategy,
    activate_new_strategy,
    load_last_context,
)

HERE = os.path.dirname(__file__)
REASONER_PAYLOAD_PATH = os.environ.get("REASONER_PAYLOAD_PATH", os.path.join(HERE, "payload_reasoner.json"))

# Initialize LM Studio client (same host) - lazy initialization
_client = None

def get_lm_studio_client():
    global _client
    if _client is None:
        try:
            _client = OpenAI(
                base_url=os.environ.get("LM_STUDIO_URL", "http://127.0.0.1:1234/v1"), 
                api_key=os.environ.get("LM_STUDIO_API_KEY", "lm-studio")
            )
        except Exception as e:
            logger.error(f"Error inicializando cliente LM Studio: {e}")
            _client = None
    return _client


def _load_payload() -> Dict[str, Any]:
    with open(REASONER_PAYLOAD_PATH, encoding="utf-8") as f:
        return json.load(f)


def _build_reasoner_messages(chat_id: str, turns: int = 30) -> List[Dict[str, str]]:
    profile = get_profile(chat_id)
    active = get_active_strategy(chat_id)
    history = load_last_context(chat_id) or []
    # Truncate to last N turns
    history_tail = history[-turns:]

    messages: List[Dict[str, str]] = []
    # System messages are already present in payload template; here we add context for the analyst
    if profile:
        if (profile.objective or '').strip():
            messages.append({"role": "system", "content": f"Objetivo del chat: {profile.objective}"})
        if (profile.instructions or '').strip():
            messages.append({"role": "system", "content": f"Instrucciones del perfil: {profile.instructions}"})
    if active and (active.strategy_text or '').strip():
        messages.append({"role": "system", "content": f"Estrategia vigente (versión {active.version}):\n{active.strategy_text}"})

    # Provide a compact snapshot of recent dialog for analysis
    snapshot_lines: List[str] = []
    for m in history_tail:
        role = m.get('role', 'user')
        content = m.get('content', '')
        snapshot_lines.append(f"{role}: {content}")
    snapshot = "\n".join(snapshot_lines)

    messages.append({
        "role": "user",
        "content": (
            "Analiza el siguiente snapshot de la conversación reciente y el objetivo dado. "
            "Propón una estrategia concreta para los próximos 10 mensajes del respondedor.\n\n"
            f"SNAPSHOT (reciente):\n{snapshot}"
        )
    })

    return messages, snapshot


def run_reasoner_for_chat(chat_id: str) -> int:
    payload = _load_payload()
    # Clone payload and append dynamic messages
    payload = payload.copy()
    payload["messages"] = list(payload.get("messages", []))
    messages, snapshot = _build_reasoner_messages(chat_id)
    payload["messages"].extend(messages)

    client = get_lm_studio_client()
    if client is None:
        logger.error("LM Studio cliente no disponible para update_chat_context_and_profile")
        return
        
    resp = client.chat.completions.create(**payload)
    strategy_text = resp.choices[0].message.content

    # Save as new active strategy (with snapshot stored for audit)
    version = activate_new_strategy(chat_id, strategy_text=strategy_text, source_snapshot=snapshot)
    return version


# -------------------------------------------------------------
# New: Update perfil/contexto files + persist strategy in DB
# -------------------------------------------------------------
def update_chat_context_and_profile(chat_id: str) -> dict:
    """Runs the reasoner to produce:
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

    perfil_text = []
    if profile:
        if (profile.initial_context or '').strip():
            perfil_text.append(f"Contexto inicial: {profile.initial_context}")
        if (profile.objective or '').strip():
            perfil_text.append(f"Objetivo: {profile.objective}")
        if (profile.instructions or '').strip():
            perfil_text.append(f"Instrucciones: {profile.instructions}")
    perfil_text = "\n".join(perfil_text) or "(sin perfil)"

    estrategia_prev = (active.strategy_text if active and (active.strategy_text or '').strip() else "(sin estrategia previa)")

    snapshot_lines = []
    for m in tail:
        role = m.get('role', 'user')
        content = m.get('content', '')
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

    payload["messages"].extend([
        {"role": "system", "content": instructions},
        {"role": "user", "content": f"Perfil actual del chat:\n{perfil_text}"},
        {"role": "user", "content": f"Estrategia vigente:\n{estrategia_prev}"},
        {"role": "user", "content": f"Snapshot reciente:\n{snapshot}"},
    ])

    # 2) Call model
    client = get_lm_studio_client()
    if client is None:
        logger.error("LM Studio cliente no disponible para reason_and_update_profile")
        return
        
    resp = client.chat.completions.create(**payload)
    txt = resp.choices[0].message.content or ""

    # 3) Parse JSON
    data = {"perfil_update": "", "contexto_prioritario": "", "estrategia": ""}
    try:
        data.update(json.loads(txt))
    except Exception:
        # Fallback: attempt naive section splits
        # Look for keys labels in plain text
        def _extract(label):
            import re
            m = re.search(label + r"\s*:\s*(.+)", txt, re.IGNORECASE | re.DOTALL)
            return (m.group(1).strip() if m else "")
        data["perfil_update"] = _extract("perfil_update")
        data["contexto_prioritario"] = _extract("contexto_prioritario")
        data["estrategia"] = _extract("estrategia")

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
    except Exception:
        pass

    # perfil: append update with timestamp
    try:
        if perfil_update:
            perfil_path = os.path.join(chat_dir, "perfil.txt")
            existing = ""
            if os.path.exists(perfil_path):
                try:
                    with open(perfil_path, "r", encoding="utf-8") as f:
                        existing = f.read()
                except Exception:
                    existing = ""
            stamp = datetime.utcnow().isoformat()
            appended = (existing + ("\n\n" if existing else "") + f"[Actualización {stamp}]\n" + perfil_update).strip()
            with open(perfil_path, "w", encoding="utf-8") as f:
                f.write(appended)
            wrote_perfil = True
    except Exception:
        pass

    # 5) Persist to DB
    version = activate_new_strategy(chat_id, strategy_text=estrategia_text or estrategia_prev, source_snapshot=snapshot)

    # Mirror contexto prioritario into ChatProfile.initial_context for faster access
    try:
        from admin_db import get_session as _gs
        from models import ChatProfile as _CP
        sess = _gs()
        prof = sess.get(_CP, chat_id) or _CP(chat_id=chat_id)
        prof.initial_context = contexto_prioritario or prof.initial_context or ""
        # keep existing objective/instructions
        prof.is_ready = True
        prof.updated_at = datetime.utcnow()
        sess.add(prof)
        sess.commit()
        sess.close()
    except Exception:
        pass

    return {
        "version": version,
        "wrote_contexto": wrote_contexto,
        "wrote_perfil": wrote_perfil,
    }
