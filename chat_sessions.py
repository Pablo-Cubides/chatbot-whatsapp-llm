import json
import os
from datetime import datetime

from admin_db import initialize_schema, get_session
from models import (
    Conversation,
    Contact,
    ChatProfile,
    ChatCounter,
    ChatStrategy,
)
from crypto import encrypt_text, decrypt_text


# Compatibilidad: inicializa esquema SQLAlchemy al importar
def initialize_db():
    initialize_schema()


def save_context(chat_id, context):
    """Guarda una nueva entrada de contexto para un chat (comportamiento append).
    Mantiene la misma firma que antes."""
    session = get_session()
    context_json = json.dumps(context, ensure_ascii=False)
    enc = encrypt_text(context_json)
    conv = Conversation(chat_id=chat_id, context=enc, timestamp=datetime.utcnow())
    session.add(conv)
    session.commit()
    session.close()


def load_last_context(chat_id):
    session = get_session()
    row = (
        session.query(Conversation)
        .filter(Conversation.chat_id == chat_id)
        .order_by(Conversation.timestamp.desc())
        .first()
    )
    session.close()
    if row:
        try:
            dec = decrypt_text(row.context)
            return json.loads(dec)
        except Exception:
            return []
    return []


def clear_conversation_history(chat_id: str) -> int:
    """Borra TODO el historial (tabla conversations) para un chat_id dado.
    Devuelve el número de filas eliminadas."""
    session = get_session()
    try:
        q = session.query(Conversation).filter(Conversation.chat_id == chat_id)
        count = q.count()
        q.delete(synchronize_session=False)
        session.commit()
        return count
    finally:
        session.close()


def clear_all_conversation_histories() -> int:
    """Borra TODO el historial de TODAS las conversaciones.
    Devuelve el número de filas eliminadas."""
    session = get_session()
    try:
        count = session.query(Conversation).count()
        session.query(Conversation).delete(synchronize_session=False)
        session.commit()
        return count
    finally:
        session.close()


# Inicializar al importar para no romper expectativas actuales
initialize_db()


# ------------------------ Two-agent pipeline helpers ------------------------

def add_or_update_contact(chat_id: str, name: str = None, auto_enabled: bool = True):
    session = get_session()
    try:
        c = session.get(Contact, chat_id)
        if not c:
            c = Contact(chat_id=chat_id)
            session.add(c)
        c.name = name
        c.auto_enabled = bool(auto_enabled)
        c.updated_at = datetime.utcnow()
        session.commit()
    finally:
        session.close()


def upsert_profile(chat_id: str, initial_context: str, objective: str, instructions: str = "", is_ready: bool = True):
    session = get_session()
    try:
        p = session.get(ChatProfile, chat_id)
        if not p:
            p = ChatProfile(chat_id=chat_id)
            session.add(p)
        p.initial_context = initial_context or ""
        p.objective = objective or ""
        p.instructions = instructions or ""
        p.is_ready = bool(is_ready)
        p.updated_at = datetime.utcnow()
        # ensure a counter exists
        ctr = session.get(ChatCounter, chat_id)
        if not ctr:
            ctr = ChatCounter(chat_id=chat_id, assistant_replies_count=0, strategy_version=0)
            session.add(ctr)
        session.commit()
    finally:
        session.close()


def get_profile(chat_id: str):
    session = get_session()
    try:
        return session.get(ChatProfile, chat_id)
    finally:
        session.close()


def is_ready_to_reply(chat_id: str) -> bool:
    session = get_session()
    try:
        c = session.get(Contact, chat_id)
        p = session.get(ChatProfile, chat_id)
        return bool(c and c.auto_enabled and p and p.is_ready)
    finally:
        session.close()


def increment_reply_counter(chat_id: str) -> int:
    session = get_session()
    try:
        ctr = session.get(ChatCounter, chat_id)
        if not ctr:
            ctr = ChatCounter(chat_id=chat_id, assistant_replies_count=0)
            session.add(ctr)
        ctr.assistant_replies_count = int(ctr.assistant_replies_count or 0) + 1
        session.commit()
        return ctr.assistant_replies_count
    finally:
        session.close()


def reset_reply_counter(chat_id: str):
    session = get_session()
    try:
        ctr = session.get(ChatCounter, chat_id)
        if not ctr:
            ctr = ChatCounter(chat_id=chat_id)
            session.add(ctr)
        ctr.assistant_replies_count = 0
        session.commit()
    finally:
        session.close()


def get_reply_counter(chat_id: str) -> int:
    session = get_session()
    try:
        ctr = session.get(ChatCounter, chat_id)
        return int(ctr.assistant_replies_count or 0) if ctr else 0
    finally:
        session.close()


def get_active_strategy(chat_id: str):
    session = get_session()
    try:
        s = (
            session.query(ChatStrategy)
            .filter(ChatStrategy.chat_id == chat_id, ChatStrategy.is_active == True)
            .order_by(ChatStrategy.version.desc(), ChatStrategy.created_at.desc())
            .first()
        )
        return s
    finally:
        session.close()


def activate_new_strategy(chat_id: str, strategy_text: str, source_snapshot: str = None) -> int:
    session = get_session()
    try:
        # deactivate previous
        session.query(ChatStrategy).filter(ChatStrategy.chat_id == chat_id, ChatStrategy.is_active == True).update({"is_active": False})
        # next version
        last = (
            session.query(ChatStrategy)
            .filter(ChatStrategy.chat_id == chat_id)
            .order_by(ChatStrategy.version.desc())
            .first()
        )
        next_ver = (last.version + 1) if last else 1
        s = ChatStrategy(chat_id=chat_id, version=next_ver, strategy_text=strategy_text, source_snapshot=source_snapshot, is_active=True)
        session.add(s)
        # update counters
        ctr = session.get(ChatCounter, chat_id)
        if not ctr:
            ctr = ChatCounter(chat_id=chat_id)
            session.add(ctr)
        from datetime import datetime as _dt
        ctr.strategy_version = next_ver
        ctr.last_reasoned_at = _dt.utcnow()
        session.commit()
        return next_ver
    finally:
        session.close()
