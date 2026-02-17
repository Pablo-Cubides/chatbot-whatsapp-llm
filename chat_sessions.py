"""Persistencia y utilidades de sesiones de chat.

Centraliza operaciones de historial, perfilado y estrategia por contacto.
"""

import contextlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete

from admin_db import get_session, initialize_schema

from crypto import decrypt_text, encrypt_text
from models import (
    ChatCounter,
    ChatProfile,
    ChatStrategy,
    Contact,
    Conversation,
)


# Compatibilidad: inicializa esquema SQLAlchemy al importar
def initialize_db() -> None:
    """Inicializa el esquema de base de datos al importar el módulo."""
    initialize_schema()


def save_context(chat_id: str, context: list[dict[str, Any]]) -> None:
    """Guarda una nueva entrada de contexto para un chat (comportamiento append).
    Mantiene la misma firma que antes."""
    session = get_session()
    try:
        context_json = json.dumps(context, ensure_ascii=False)
        enc = encrypt_text(context_json)
        conv = Conversation(chat_id=chat_id, context=enc, timestamp=datetime.now(timezone.utc))
        session.add(conv)
        session.commit()
        with contextlib.suppress(Exception):
            prune_conversation_rows_ttl_and_cap(chat_id=chat_id)
    finally:
        session.close()


def prune_conversation_rows_ttl_and_cap(chat_id: str | None = None) -> int:
    """Poda filas por TTL global y por tope de filas por chat para evitar crecimiento indefinido."""
    session = get_session()
    try:
        deleted = 0
        batch_size = max(100, int(os.getenv("CONVERSATION_PRUNE_BATCH_SIZE", "1000") or "1000"))

        ttl_days = max(0, int(os.getenv("CONVERSATION_TTL_DAYS", "30") or "30"))
        max_rows_per_chat = max(1, int(os.getenv("CONVERSATION_MAX_ROWS_PER_CHAT", "200") or "200"))

        # 1) TTL global
        if ttl_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
            while True:
                ttl_ids = [
                    row[0]
                    for row in (
                        session.query(Conversation.id)
                        .filter(Conversation.timestamp < cutoff)
                        .order_by(Conversation.id.asc())
                        .limit(batch_size)
                        .all()
                    )
                ]
                if not ttl_ids:
                    break
                result = session.execute(delete(Conversation).where(Conversation.id.in_(ttl_ids)))
                session.commit()
                deleted += int(result.rowcount or 0)

        # 2) Cap por chat (aplica al chat actual si viene indicado)
        target_chat_ids: list[str] = []
        if chat_id:
            target_chat_ids = [chat_id]
        else:
            target_chat_ids = [row[0] for row in session.query(Conversation.chat_id).filter(Conversation.chat_id.isnot(None)).distinct().all()]

        for cid in target_chat_ids:
            if not cid:
                continue
            total_rows = int(session.query(Conversation).filter(Conversation.chat_id == cid).count())
            overflow = total_rows - max_rows_per_chat
            if overflow <= 0:
                continue

            while overflow > 0:
                to_delete = min(batch_size, overflow)
                stale_ids = [
                    row[0]
                    for row in (
                        session.query(Conversation.id)
                        .filter(Conversation.chat_id == cid)
                        .order_by(Conversation.timestamp.asc(), Conversation.id.asc())
                        .limit(to_delete)
                        .all()
                    )
                ]
                if not stale_ids:
                    break
                result = session.execute(delete(Conversation).where(Conversation.id.in_(stale_ids)))
                session.commit()
                affected = int(result.rowcount or 0)
                deleted += affected
                overflow -= affected

        return deleted
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def load_last_context(chat_id: str) -> list[dict[str, Any]]:
    """Carga el último snapshot de contexto para un `chat_id` dado."""
    session = get_session()
    try:
        row = (
            session.query(Conversation)
            .filter(Conversation.chat_id == chat_id)
            .order_by(Conversation.timestamp.desc())
            .first()
        )
    finally:
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


def add_or_update_contact(chat_id: str, name: str | None = None, auto_enabled: bool = True) -> None:
    """Crea o actualiza un contacto habilitado para automatización."""
    session = get_session()
    try:
        c = session.get(Contact, chat_id)
        if not c:
            c = Contact(chat_id=chat_id)
            session.add(c)
        c.name = name
        c.auto_enabled = bool(auto_enabled)
        c.updated_at = datetime.now(timezone.utc)
        session.commit()
    finally:
        session.close()


def upsert_profile(
    chat_id: str,
    initial_context: str,
    objective: str,
    instructions: str = "",
    is_ready: bool = True,
) -> None:
    """Crea o actualiza perfil de conversación y asegura contador asociado."""
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
        p.updated_at = datetime.now(timezone.utc)
        # ensure a counter exists
        ctr = session.get(ChatCounter, chat_id)
        if not ctr:
            ctr = ChatCounter(chat_id=chat_id, assistant_replies_count=0, strategy_version=0)
            session.add(ctr)
        session.commit()
    finally:
        session.close()


def get_profile(chat_id: str) -> ChatProfile | None:
    """Obtiene el perfil de chat por `chat_id` o `None` si no existe."""
    session = get_session()
    try:
        return session.get(ChatProfile, chat_id)
    finally:
        session.close()


def is_ready_to_reply(chat_id: str) -> bool:
    """Indica si el chat está habilitado y listo para responder automáticamente."""
    session = get_session()
    try:
        c = session.get(Contact, chat_id)
        p = session.get(ChatProfile, chat_id)
        return bool(c and c.auto_enabled and p and p.is_ready)
    finally:
        session.close()


def increment_reply_counter(chat_id: str) -> int:
    """Incrementa y devuelve el contador de respuestas del asistente por chat."""
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


def reset_reply_counter(chat_id: str) -> None:
    """Reinicia a cero el contador de respuestas del asistente por chat."""
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
    """Devuelve el contador de respuestas del asistente para un chat."""
    session = get_session()
    try:
        ctr = session.get(ChatCounter, chat_id)
        return int(ctr.assistant_replies_count or 0) if ctr else 0
    finally:
        session.close()


def get_active_strategy(chat_id: str) -> ChatStrategy | None:
    """Obtiene la estrategia activa más reciente para un chat."""
    session = get_session()
    try:
        s = (
            session.query(ChatStrategy)
            .filter(ChatStrategy.chat_id == chat_id, ChatStrategy.is_active)
            .order_by(ChatStrategy.version.desc(), ChatStrategy.created_at.desc())
            .first()
        )
        return s
    finally:
        session.close()


def activate_new_strategy(chat_id: str, strategy_text: str, source_snapshot: str | None = None) -> int:
    """Desactiva la estrategia previa y activa una nueva versión."""
    session = get_session()
    try:
        # deactivate previous
        session.query(ChatStrategy).filter(ChatStrategy.chat_id == chat_id, ChatStrategy.is_active).update(
            {"is_active": False}
        )
        # next version
        last = (
            session.query(ChatStrategy).filter(ChatStrategy.chat_id == chat_id).order_by(ChatStrategy.version.desc()).first()
        )
        next_ver = (last.version + 1) if last else 1
        s = ChatStrategy(
            chat_id=chat_id, version=next_ver, strategy_text=strategy_text, source_snapshot=source_snapshot, is_active=True
        )
        session.add(s)
        # update counters
        ctr = session.get(ChatCounter, chat_id)
        if not ctr:
            ctr = ChatCounter(chat_id=chat_id)
            session.add(ctr)
        from datetime import datetime as _dt

        ctr.strategy_version = next_ver
        ctr.last_reasoned_at = _dt.now(timezone.utc)
        session.commit()
        return next_ver
    finally:
        session.close()


def load_recent_conversations(limit: int = 25, min_messages: int = 2) -> list[dict[str, Any]]:
    """Retorna snapshots recientes (último contexto por chat) para análisis adaptativo."""
    session = get_session()
    try:
        safe_limit = max(1, min(int(limit), 200))
        rows = session.query(Conversation).order_by(Conversation.timestamp.desc()).limit(safe_limit * 4).all()

        snapshots: list[dict[str, Any]] = []
        seen_chats: set[str] = set()

        for row in rows:
            if row.chat_id in seen_chats:
                continue

            try:
                decrypted = decrypt_text(row.context)
                messages = json.loads(decrypted)
            except Exception:
                messages = []

            if not isinstance(messages, list) or len(messages) < min_messages:
                continue

            snapshots.append(
                {
                    "session_id": f"{row.chat_id}_{int(row.timestamp.timestamp()) if row.timestamp else 0}",
                    "contact": row.chat_id,
                    "messages": messages,
                }
            )
            seen_chats.add(row.chat_id)

            if len(snapshots) >= safe_limit:
                break

        return snapshots
    finally:
        session.close()


def prune_orphan_conversation_rows(limit: int = 500) -> int:
    """Eliminar filas huérfanas de conversaciones sin `chat_id` válido o sin contacto asociado."""
    session = get_session()
    try:
        safe_limit = max(1, min(int(limit), 5000))

        orphans_no_chat_id = (
            session.query(Conversation)
            .filter((Conversation.chat_id == None) | (Conversation.chat_id == ""))  # noqa: E711
            .limit(safe_limit)
            .all()
        )

        existing_contacts = {row[0] for row in session.query(Contact.chat_id).all()}
        candidate_rows = (
            session.query(Conversation)
            .filter(Conversation.chat_id.isnot(None))
            .order_by(Conversation.timestamp.asc())
            .limit(safe_limit)
            .all()
        )

        orphan_without_contact = [row for row in candidate_rows if row.chat_id and row.chat_id not in existing_contacts]
        to_delete = orphans_no_chat_id + orphan_without_contact

        if not to_delete:
            return 0

        deleted = 0
        for row in to_delete:
            session.delete(row)
            deleted += 1

        session.commit()
        return deleted
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
