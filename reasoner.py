import json
import os
from datetime import datetime
from openai import OpenAI

from admin_db import get_session
from models import Conversation
import chat_sessions as cs

HERE = os.path.dirname(__file__)
REASONER_PAYLOAD_PATH = os.environ.get("REASONER_PAYLOAD_PATH", os.path.join(HERE, "payload_reasoner.json"))

# LM Studio client
client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")


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
    """
    profile = cs.get_profile(chat_id)
    prev = cs.get_active_strategy(chat_id)

    # Build prompt pieces
    profile_block = []
    if profile and (profile.initial_context or '').strip():
        profile_block.append(f"Contexto inicial: {profile.initial_context}")
    if profile and (profile.objective or '').strip():
        profile_block.append(f"Objetivo: {profile.objective}")
    if profile and (profile.instructions or '').strip():
        profile_block.append(f"Instrucciones: {profile.instructions}")
    profile_text = "\n".join(profile_block) or "(sin perfil)"

    prev_text = prev.strategy_text if prev and (prev.strategy_text or '').strip() else "(sin estrategia previa)"
    convo_snapshot = _last_turns(chat_id, n_turns=40)

    # Build payload
    payload = _load_payload_template()
    messages = list(payload.get("messages", []))
    messages += [
        {"role": "system", "content": "No hables con el usuario. Responde solo con la estrategia."},
        {"role": "user", "content": f"Perfil del chat (resumen):\n{profile_text}"},
        {"role": "user", "content": f"Estrategia vigente (si la hay):\n{prev_text}"},
        {"role": "user", "content": f"Extracto de la conversación (últimos turnos):\n{convo_snapshot}"},
        {"role": "user", "content": "Formula la ESTRATEGIA OPERATIVA para los próximos 10 mensajes del bot respondedor."}
    ]
    payload["messages"] = messages

    # Call LM Studio
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

# Initialize LM Studio client (same host)
client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")


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

    resp = client.chat.completions.create(**payload)
    strategy_text = resp.choices[0].message.content

    # Save as new active strategy (with snapshot stored for audit)
    version = activate_new_strategy(chat_id, strategy_text=strategy_text, source_snapshot=snapshot)
    return version
