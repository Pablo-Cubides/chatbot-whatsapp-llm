"""
📬 Sistema de Cola Unificada para Mensajes
Gestión centralizada de todos los mensajes salientes (bulk, scheduled, manual)
"""

import contextlib
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from src.models.admin_db import get_session
from src.models.models import Base

logger = logging.getLogger(__name__)


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

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(100), unique=True, nullable=False, index=True)
    chat_id = Column(String(200), nullable=False, index=True)
    message = Column(Text, nullable=False)
    status = Column(String(20), default=MessageStatus.PENDING, nullable=False, index=True)
    priority = Column(Integer, default=0, nullable=False)
    scheduled_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    total_messages = Column(Integer, default=0, nullable=False)
    sent_messages = Column(Integer, default=0, nullable=False)
    failed_messages = Column(Integer, default=0, nullable=False)
    extra_data = Column(JSON, nullable=True)


class QueueManager:
    """Gestor de la cola de mensajes"""

    def __init__(self):
        self.json_backup_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "manual_queue.json"
        )
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

            # Backup en JSON para compatibilidad
            self._backup_to_json(queued_msg)

            logger.info(f"✅ Mensaje encolado: {message_id} para {chat_id}")
            return message_id

        except Exception as e:
            logger.error(f"❌ Error encolando mensaje: {e}")
            with contextlib.suppress(Exception):
                session.rollback()
            raise
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
                query = query.filter((QueuedMessage.scheduled_at is None) | (QueuedMessage.scheduled_at <= now))
            else:
                query = query.filter(QueuedMessage.scheduled_at is None)

            query = query.order_by(QueuedMessage.priority.desc(), QueuedMessage.created_at.asc()).limit(limit)

            messages = query.all()
            session.close()

            return [self._message_to_dict(msg) for msg in messages]

        except Exception as e:
            logger.error(f"❌ Error obteniendo mensajes pendientes: {e}")
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
            logger.error(f"❌ Error marcando mensaje como enviado: {e}")
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
            logger.error(f"❌ Error marcando mensaje como fallido: {e}")
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

            logger.info(f"✅ Campaña creada: {campaign_id}")
            return campaign_id

        except Exception as e:
            logger.error(f"❌ Error creando campaña: {e}")
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
            logger.error(f"❌ Error obteniendo estado de campaña: {e}")
            return None

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

            if campaign:
                campaign.status = "cancelled"

            # Cancelar mensajes pendientes de esta campaña
            # Obtener todos los mensajes pendientes y filtrar por campaign_id
            pending_messages = (
                session.query(QueuedMessage)
                .filter(QueuedMessage.status.in_([MessageStatus.PENDING, MessageStatus.RETRY]))
                .all()
            )

            for msg in pending_messages:
                if msg.extra_data and msg.extra_data.get("campaign_id") == campaign_id:
                    msg.status = MessageStatus.CANCELLED

            session.commit()
            session.close()
            return True

        except Exception as e:
            logger.error(f"❌ Error cancelando campaña: {e}")
            return False

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
            logger.error(f"❌ Error actualizando estado de campaña: {e}")
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
            logger.error(f"❌ Error actualizando stats de campaña: {e}")

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

    def _backup_to_json(self, msg: QueuedMessage):
        """Backup de mensaje en JSON para compatibilidad"""
        try:
            os.makedirs(os.path.dirname(self.json_backup_path), exist_ok=True)

            # Leer queue actual
            queue = []
            if os.path.exists(self.json_backup_path):
                with open(self.json_backup_path, encoding="utf-8") as f:
                    queue = json.load(f)

            # Agregar nuevo mensaje
            queue.append(
                {
                    "id": msg.message_id,
                    "chat_id": msg.chat_id,
                    "message": msg.message,
                    "timestamp": msg.created_at.isoformat(),
                    "status": msg.status,
                }
            )

            # Guardar
            with open(self.json_backup_path, "w", encoding="utf-8") as f:
                json.dump(queue, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.warning(f"⚠️ No se pudo hacer backup JSON: {e}")


# Instancia global
queue_manager = QueueManager()
