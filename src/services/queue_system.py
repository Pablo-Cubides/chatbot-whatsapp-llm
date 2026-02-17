"""
📬 Sistema de Cola Unificada para Mensajes
Gestión centralizada de todos los mensajes salientes (bulk, scheduled, manual)
"""

import contextlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import Index, or_
from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from src.models.admin_db import get_session
from src.models.models import Base

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MessageStatus(str, Enum):
    """Estados posibles de un mensaje"""

    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"


class QueuedMessage(Base):
    """Modelo de mensaje en cola"""

    __tablename__ = "message_queue"
    __table_args__ = (Index("ix_queued_message_status_scheduled", "status", "scheduled_at"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(100), unique=True, nullable=False, index=True)
    chat_id = Column(String(200), nullable=False, index=True)
    message = Column(Text, nullable=False)
    status = Column(String(20), default=MessageStatus.PENDING, nullable=False, index=True)
    priority = Column(Integer, default=0, nullable=False)
    scheduled_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    error_message = Column(Text, nullable=True)
    extra_data = Column(JSON, nullable=True)  # campaign_id, media, etc.


class Campaign(Base):
    """Modelo de campaña de mensajes"""

    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    status = Column(String(20), default="active", nullable=False, index=True)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    total_messages = Column(Integer, default=0, nullable=False)
    sent_messages = Column(Integer, default=0, nullable=False)
    failed_messages = Column(Integer, default=0, nullable=False)
    extra_data = Column(JSON, nullable=True)


class QueueManager:
    """Gestor de la cola de mensajes"""

    def __init__(self):
        logger.info("📬 Queue Manager inicializado")

    def enqueue_message(
        self,
        chat_id: str,
        message: str,
        when: Optional[datetime] = None,
        priority: int = 0,
        metadata: Optional[dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> str:
        """
        Encolar un mensaje para envío

        Args:
            chat_id: ID del chat destino
            message: Texto del mensaje
            when: Fecha/hora de envío (None = inmediato)
            priority: Prioridad (mayor = más urgente)
            metadata: Datos adicionales (campaign_id, media, etc.)
            max_retries: Reintentos máximos

        Returns:
            message_id generado
        """
        try:
            session = get_session()

            # Generar ID único con UUID
            message_id = f"msg_{uuid.uuid4().hex[:16]}"

            # Crear entrada en BD
            queued_msg = QueuedMessage(
                message_id=message_id,
                chat_id=chat_id,
                message=message,
                status=MessageStatus.PENDING,
                priority=priority,
                scheduled_at=when,
                extra_data=metadata or {},
                max_retries=max_retries,
            )

            session.add(queued_msg)
            session.commit()

            logger.info("✅ Mensaje encolado: %s para %s", message_id, chat_id)
            return message_id

        except Exception as e:
            logger.error("❌ Error encolando mensaje: %s", e)
            with contextlib.suppress(Exception):
                session.rollback()
            raise
        finally:
            with contextlib.suppress(Exception):
                session.close()

    def enqueue_bulk_messages(self, rows: list[dict[str, Any]]) -> list[str]:
        """Bulk enqueue messages with a single DB transaction for campaign-scale throughput."""
        if not rows:
            return []

        session = get_session()
        try:
            prepared: list[QueuedMessage] = []
            ids: list[str] = []

            for row in rows:
                message_id = f"msg_{uuid.uuid4().hex[:16]}"
                ids.append(message_id)
                prepared.append(
                    QueuedMessage(
                        message_id=message_id,
                        chat_id=str(row.get("chat_id") or "").strip(),
                        message=str(row.get("message") or ""),
                        status=MessageStatus.PENDING,
                        priority=int(row.get("priority") or 0),
                        scheduled_at=row.get("when"),
                        extra_data=row.get("metadata") or {},
                        max_retries=max(1, int(row.get("max_retries") or 3)),
                    )
                )

            session.bulk_save_objects(prepared)
            session.commit()
            return ids
        except Exception as e:
            logger.error("❌ Error encolando bulk messages: %s", e)
            with contextlib.suppress(Exception):
                session.rollback()
            return []
        finally:
            with contextlib.suppress(Exception):
                session.close()

    def get_pending_messages(self, limit: int = 10, include_scheduled: bool = True) -> list[dict[str, Any]]:
        """
        Obtener mensajes pendientes para procesar

        Args:
            limit: Cantidad máxima a retornar
            include_scheduled: Incluir mensajes programados cuya hora llegó

        Returns:
            Lista de mensajes pendientes
        """
        try:
            session = get_session()

            query = session.query(QueuedMessage).filter(QueuedMessage.status == MessageStatus.PENDING)

            if include_scheduled:
                # Solo incluir mensajes cuya hora llegó
                now = datetime.now(timezone.utc)
                query = query.filter(or_(QueuedMessage.scheduled_at.is_(None), QueuedMessage.scheduled_at <= now))
            else:
                query = query.filter(QueuedMessage.scheduled_at.is_(None))

            query = query.order_by(QueuedMessage.priority.desc(), QueuedMessage.created_at.asc()).limit(limit)

            messages = query.all()
            session.close()

            return [self._message_to_dict(msg) for msg in messages]

        except Exception as e:
            logger.error("❌ Error obteniendo mensajes pendientes: %s", e)
            return []

    def mark_as_sent(self, message_id: str) -> bool:
        """Marcar mensaje como enviado"""
        try:
            session = get_session()

            msg = session.query(QueuedMessage).filter(QueuedMessage.message_id == message_id).first()

            if msg:
                msg.status = MessageStatus.SENT
                msg.sent_at = datetime.now(timezone.utc)
                msg.processed_at = datetime.now(timezone.utc)
                session.commit()

                # Actualizar campaign si aplica
                if msg.extra_data and msg.extra_data.get("campaign_id"):
                    self._update_campaign_stats(msg.extra_data["campaign_id"], sent=True)

            session.close()
            return True

        except Exception as e:
            logger.error("❌ Error marcando mensaje como enviado: %s", e)
            return False

    def mark_as_failed(self, message_id: str, error: str) -> bool:
        """Marcar mensaje como fallido"""
        try:
            session = get_session()

            msg = session.query(QueuedMessage).filter(QueuedMessage.message_id == message_id).first()

            if msg:
                msg.retry_count += 1
                msg.error_message = error
                msg.processed_at = datetime.now(timezone.utc)

                if msg.retry_count >= msg.max_retries:
                    msg.status = MessageStatus.FAILED
                    # Actualizar campaign
                    if msg.extra_data and msg.extra_data.get("campaign_id"):
                        self._update_campaign_stats(msg.extra_data["campaign_id"], failed=True)
                else:
                    msg.status = MessageStatus.RETRY
                    # Reprogramar para dentro de X minutos
                    msg.scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=5 * msg.retry_count)

                session.commit()

            session.close()
            return True

        except Exception as e:
            logger.error("❌ Error marcando mensaje como fallido: %s", e)
            return False

    def create_campaign(
        self, name: str, created_by: str, total_messages: int, metadata: Optional[dict[str, Any]] = None
    ) -> str:
        """Crear una nueva campaña"""
        try:
            session = get_session()

            # Generar ID único con UUID
            campaign_id = f"camp_{uuid.uuid4().hex[:16]}"

            campaign = Campaign(
                campaign_id=campaign_id,
                name=name,
                status="active",
                created_by=created_by,
                total_messages=total_messages,
                extra_data=metadata or {},
            )

            session.add(campaign)
            session.commit()
            session.close()

            logger.info("✅ Campaña creada: %s", campaign_id)
            return campaign_id

        except Exception as e:
            logger.error("❌ Error creando campaña: %s", e)
            raise

    def get_campaign_status(self, campaign_id: str) -> Optional[dict[str, Any]]:
        """Obtener estado de una campaña"""
        try:
            session = get_session()

            campaign = session.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()

            if not campaign:
                session.close()
                return None

            result = {
                "campaign_id": campaign.campaign_id,
                "name": campaign.name,
                "status": campaign.status,
                "created_by": campaign.created_by,
                "created_at": campaign.created_at.isoformat(),
                "total_messages": campaign.total_messages,
                "sent_messages": campaign.sent_messages,
                "failed_messages": campaign.failed_messages,
                "pending_messages": campaign.total_messages - campaign.sent_messages - campaign.failed_messages,
                "success_rate": (campaign.sent_messages / campaign.total_messages * 100) if campaign.total_messages > 0 else 0,
                "metadata": campaign.extra_data,  # Mantener 'metadata' en API por compatibilidad
            }

            session.close()
            return result

        except Exception as e:
            logger.error("❌ Error obteniendo estado de campaña: %s", e)
            return None

    def list_campaigns(self, status: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
        """Listar campañas con filtro opcional por estado."""
        try:
            session = get_session()
            query = session.query(Campaign)
            if status:
                query = query.filter(Campaign.status == status)

            campaigns = query.order_by(Campaign.created_at.desc()).limit(limit).all()
            return [
                {
                    "campaign_id": camp.campaign_id,
                    "name": camp.name,
                    "status": camp.status,
                    "created_by": camp.created_by,
                    "created_at": camp.created_at.isoformat(),
                    "total_messages": camp.total_messages,
                    "sent_messages": camp.sent_messages,
                    "failed_messages": camp.failed_messages,
                    "pending_messages": camp.total_messages - camp.sent_messages - camp.failed_messages,
                    "metadata": camp.extra_data,
                }
                for camp in campaigns
            ]
        except Exception as e:
            logger.error("❌ Error listando campañas: %s", e)
            return []
        finally:
            with contextlib.suppress(Exception):
                session.close()

    def pause_campaign(self, campaign_id: str) -> bool:
        """Pausar una campaña"""
        return self._update_campaign_status(campaign_id, "paused")

    def resume_campaign(self, campaign_id: str) -> bool:
        """Reanudar una campaña"""
        return self._update_campaign_status(campaign_id, "active")

    def cancel_campaign(self, campaign_id: str) -> bool:
        """Cancelar una campaña"""
        try:
            session = get_session()

            # Actualizar estado de campaña
            campaign = session.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()

            if not campaign:
                return False

            campaign.status = "cancelled"

            # Cancelar mensajes pendientes de esta campaña
            # Obtener todos los mensajes pendientes y filtrar por campaign_id
            queued_messages = (
                session.query(QueuedMessage)
                .filter(QueuedMessage.status.in_([MessageStatus.PENDING, MessageStatus.RETRY]))
                .all()
            )

            for msg in queued_messages:
                if msg.extra_data and msg.extra_data.get("campaign_id") == campaign_id:
                    msg.status = MessageStatus.CANCELLED
                    msg.processed_at = datetime.now(timezone.utc)

            session.commit()
            return True

        except Exception as e:
            logger.error("❌ Error cancelando campaña: %s", e)
            with contextlib.suppress(Exception):
                session.rollback()
            return False
        finally:
            with contextlib.suppress(Exception):
                session.close()

    def _update_campaign_status(self, campaign_id: str, status: str) -> bool:
        """Actualizar estado de campaña"""
        try:
            session = get_session()

            campaign = session.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()

            if campaign:
                campaign.status = status
                session.commit()

            session.close()
            return True

        except Exception as e:
            logger.error("❌ Error actualizando estado de campaña: %s", e)
            return False

    def _update_campaign_stats(self, campaign_id: str, sent: bool = False, failed: bool = False):
        """Actualizar estadísticas de campaña"""
        try:
            session = get_session()

            campaign = session.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()

            if campaign:
                if sent:
                    campaign.sent_messages += 1
                if failed:
                    campaign.failed_messages += 1
                session.commit()

            session.close()

        except Exception as e:
            logger.error("❌ Error actualizando stats de campaña: %s", e)

    def _message_to_dict(self, msg: QueuedMessage) -> dict[str, Any]:
        """Convertir mensaje a diccionario"""
        return {
            "message_id": msg.message_id,
            "chat_id": msg.chat_id,
            "message": msg.message,
            "status": msg.status,
            "priority": msg.priority,
            "scheduled_at": msg.scheduled_at.isoformat() if msg.scheduled_at else None,
            "created_at": msg.created_at.isoformat(),
            "retry_count": msg.retry_count,
            "metadata": msg.extra_data,  # Mantener 'metadata' en API por compatibilidad
        }

# Instancia global
queue_manager = QueueManager()
