"""
🔇 Sistema de Transferencia Silenciosa a Humano
Transfiere conversaciones a humanos SIN que el cliente se entere
"""

import logging
import os
from datetime import datetime, timezone
from enum import Enum
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

import httpx
from sqlalchemy import String, cast, func

try:
    from src.models.admin_db import get_session
    from src.models.models import Base, SilentTransfer
except ImportError:
    # Fallback para desarrollo
    Base = None
    get_session = None
    SilentTransfer = None

logger = logging.getLogger(__name__)


def _run_async_blocking(coro):
    try:
        asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro)).result()
    except RuntimeError:
        return asyncio.run(coro)


async def _post_json_async(url: str, payload: dict[str, Any], timeout_seconds: float = 5) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        return await client.post(url, json=payload)


class TransferReason(Enum):
    """Razones de transferencia"""

    LLM_FAILURE = "llm_failure"  # Todos los LLM fallaron
    SIMPLE_QUESTION_FAIL = "simple_fail"  # Pregunta simple falló
    ETHICAL_REFUSAL = "ethical_refusal"  # LLM se negó por ética
    HIGH_VALUE_CLIENT = "high_value"  # Cliente de alto valor
    EXPLICIT_REQUEST = "explicit_request"  # Cliente pidió humano
    SUSPICION_DETECTED = "suspicion"  # Cliente sospechó bot
    NEGATIVE_EMOTION = "negative_emotion"  # Emoción muy negativa
    CRITICAL_ERROR = "critical_error"  # Error crítico del sistema


class TransferStatus(Enum):
    """Estados de transferencia"""

    PENDING = "pending"  # Esperando atención humana
    IN_PROGRESS = "in_progress"  # Humano atendiendo
    COMPLETED = "completed"  # Atención completada
    CANCELLED = "cancelled"  # Cancelada (cliente se fue)


class SilentTransferManager:
    """
    Gestiona transferencias silenciosas a humanos
    El cliente NO se entera de la transferencia
    """

    def __init__(self):
        self.enabled = os.getenv("SILENT_TRANSFER_ENABLED", "true").lower() == "true"
        self.notification_webhook = os.getenv("TRANSFER_NOTIFICATION_WEBHOOK")

        # Prioridades por razón
        self.priority_map = {
            TransferReason.SUSPICION_DETECTED: 10,  # Máxima urgencia
            TransferReason.HIGH_VALUE_CLIENT: 9,
            TransferReason.CRITICAL_ERROR: 8,
            TransferReason.NEGATIVE_EMOTION: 7,
            TransferReason.SIMPLE_QUESTION_FAIL: 6,
            TransferReason.ETHICAL_REFUSAL: 5,
            TransferReason.EXPLICIT_REQUEST: 4,
            TransferReason.LLM_FAILURE: 3,
        }

        if self.enabled:
            logger.info("🔇 Sistema de transferencia silenciosa habilitado")

    def should_transfer_silently(
        self,
        reason: TransferReason,
        user_message: str,
        conversation_history: list[dict] = None,
        context: dict[str, Any] = None,
    ) -> bool:
        """
        Determina si debe hacer transferencia silenciosa

        Criterios:
        - Preguntas simples que fallaron
        - Sospecha de bot detectada
        - Cliente de alto valor
        - Error crítico
        """
        # Siempre transferir en estos casos
        critical_reasons = [
            TransferReason.SIMPLE_QUESTION_FAIL,
            TransferReason.SUSPICION_DETECTED,
            TransferReason.CRITICAL_ERROR,
        ]

        if reason in critical_reasons:
            return True

        # Para otros casos, evaluar contexto
        if reason == TransferReason.HIGH_VALUE_CLIENT:
            return context.get("client_value", 0) > 1000

        if reason == TransferReason.NEGATIVE_EMOTION:
            return context.get("emotion_score", 0) < 0.3

        return False

    def create_transfer(
        self,
        chat_id: str,
        reason: TransferReason,
        trigger_message: str,
        conversation_history: list[dict] = None,
        metadata: dict[str, Any] = None,
        notify_client: bool = False,
    ) -> Optional[str]:
        """
        Crea una transferencia silenciosa

        Args:
            chat_id: ID del chat
            reason: Razón de la transferencia
            trigger_message: Mensaje que causó la transferencia
            conversation_history: Historial de conversación
            metadata: Metadata adicional
            notify_client: Si debe notificar al cliente (por defecto False = silencioso)

        Returns:
            transfer_id si se creó exitosamente
        """
        if not self.enabled or get_session is None:
            logger.warning("⚠️ Sistema de transferencia silenciosa no disponible")
            return None

        try:
            session = get_session()

            # Generar ID único
            transfer_id = f"transfer_{chat_id}_{int(datetime.now(timezone.utc).timestamp())}"

            # Determinar prioridad
            priority = self.priority_map.get(reason, 5)

            # Extraer contexto relevante
            context_data = {
                "last_messages": conversation_history[-10:] if conversation_history else [],
                "transfer_reason": reason.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            if metadata:
                context_data.update(metadata)

            # Crear transferencia
            transfer = SilentTransfer(
                transfer_id=transfer_id,
                chat_id=chat_id,
                reason=reason.value,
                trigger_message=trigger_message,
                conversation_context=context_data,
                status=TransferStatus.PENDING.value,
                priority=priority,
                client_notified=notify_client,
                transfer_metadata=metadata,
            )

            session.add(transfer)
            session.commit()

            logger.warning("🔇 TRANSFERENCIA SILENCIOSA creada: %s", transfer_id)
            logger.warning("   Razón: %s", reason.value)
            logger.warning("   Chat: %s", chat_id)
            logger.warning("   Mensaje: %s", trigger_message[:100])
            logger.warning("   Cliente notificado: %s", notify_client)

            # Notificar a operadores humanos
            if not notify_client:
                self._notify_operators_silent(transfer_id, chat_id, reason, trigger_message)
            else:
                self._notify_operators_explicit(transfer_id, chat_id, reason)

            session.close()
            return transfer_id

        except Exception as e:
            logger.error("❌ Error creando transferencia silenciosa: %s", e)
            try:
                session.rollback()
                session.close()
            except Exception:
                pass
            return None

    def _notify_operators_silent(self, transfer_id: str, chat_id: str, reason: TransferReason, trigger_message: str):
        """
        Notifica a operadores humanos de transferencia SILENCIOSA

        Mensaje: "URGENTE - Cliente {chat_id} requiere atención INMEDIATA
                  sin que se entere de la transferencia"
        """
        notification = {
            "type": "SILENT_TRANSFER",
            "urgency": "HIGH",
            "transfer_id": transfer_id,
            "chat_id": chat_id,
            "reason": reason.value,
            "trigger": trigger_message,
            "instructions": [
                "🚨 TRANSFERENCIA SILENCIOSA - Cliente NO sabe que fue transferido",
                "NO mencionar que es una 'transferencia'",
                "NO decir 'ya lo atiendo un humano'",
                "Continuar la conversación como si nada hubiera pasado",
                f"Contexto: {self._get_reason_explanation(reason)}",
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Log para operadores
        logger.warning("=" * 80)
        logger.warning("🚨 ALERTA DE TRANSFERENCIA SILENCIOSA")
        logger.warning("=" * 80)
        logger.warning("Transfer ID: %s", transfer_id)
        logger.warning("Chat ID: %s", chat_id)
        logger.warning("Razón: %s", reason.value)
        logger.warning("Mensaje: %s", trigger_message)
        logger.warning("")
        logger.warning("INSTRUCCIONES PARA OPERADOR HUMANO:")
        for instruction in notification["instructions"]:
            logger.warning("  %s", instruction)
        logger.warning("=" * 80)

        self._dispatch_notification(notification)

    def _notify_operators_explicit(self, transfer_id: str, chat_id: str, reason: TransferReason):
        """
        Notifica transferencia EXPLÍCITA (cliente pidió hablar con humano)
        """
        logger.info("📞 Transferencia explícita: %s - %s", transfer_id, chat_id)
        notification = {
            "type": "EXPLICIT_TRANSFER",
            "urgency": "MEDIUM",
            "transfer_id": transfer_id,
            "chat_id": chat_id,
            "reason": reason.value,
            "instructions": [
                "Cliente pidió hablar con humano",
                "Tomar conversación manualmente y confirmar atención",
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._dispatch_notification(notification)

    def _dispatch_notification(self, notification: dict[str, Any]) -> bool:
        """Enviar notificación por webhook y fallback a alerta interna."""
        delivered = False

        if self.notification_webhook:
            try:
                response = _run_async_blocking(_post_json_async(self.notification_webhook, notification, timeout_seconds=5))
                if response.status_code < 300:
                    delivered = True
                else:
                    logger.warning("⚠️ Webhook de transferencia respondió %s", response.status_code)
            except Exception as e:
                logger.error("Error enviando notificación webhook: %s", e)

        if not delivered:
            try:
                from src.services.alert_system import AlertSeverity, alert_manager

                alert_id = alert_manager.create_alert(
                    chat_id=notification.get("chat_id", "unknown"),
                    severity=AlertSeverity.HIGH.value,
                    message_text=f"Transferencia requerida: {notification.get('reason', 'unknown')}",
                    metadata={"source": "silent_transfer", "notification": notification},
                )
                delivered = bool(alert_id)
            except Exception as e:
                logger.error("Error enviando fallback de notificación: %s", e)

        if not delivered:
            logger.warning("⚠️ No se pudo entregar notificación de transferencia")

        return delivered

    def _get_reason_explanation(self, reason: TransferReason) -> str:
        """Explicación de la razón de transferencia para operadores"""
        explanations = {
            TransferReason.SIMPLE_QUESTION_FAIL: "Pregunta simple falló - El bot no pudo responder algo básico (nombre, horario, etc)",
            TransferReason.SUSPICION_DETECTED: "CRÍTICO - Cliente sospechó que habla con bot",
            TransferReason.ETHICAL_REFUSAL: "LLM se negó a responder por 'razones éticas'",
            TransferReason.LLM_FAILURE: "Todos los proveedores de IA fallaron",
            TransferReason.CRITICAL_ERROR: "Error crítico del sistema",
            TransferReason.HIGH_VALUE_CLIENT: "Cliente de alto valor requiere atención premium",
            TransferReason.NEGATIVE_EMOTION: "Cliente con emoción muy negativa",
            TransferReason.EXPLICIT_REQUEST: "Cliente pidió hablar con humano",
        }
        return explanations.get(reason, "Sin descripción")

    def get_pending_transfers(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        Obtiene transferencias pendientes para atención

        Returns:
            Lista de transferencias ordenadas por prioridad
        """
        if not self.enabled or get_session is None:
            return []

        try:
            session = get_session()

            transfers = (
                session.query(SilentTransfer)
                .filter(SilentTransfer.status == TransferStatus.PENDING.value)
                .order_by(SilentTransfer.priority.desc(), SilentTransfer.created_at.asc())
                .limit(limit)
                .all()
            )

            result = [
                {
                    "transfer_id": t.transfer_id,
                    "chat_id": t.chat_id,
                    "reason": t.reason,
                    "priority": t.priority,
                    "trigger_message": t.trigger_message,
                    "created_at": t.created_at.isoformat(),
                    "silent": not t.client_notified,
                    "waiting_time_minutes": (datetime.now(timezone.utc) - t.created_at).total_seconds() / 60,
                }
                for t in transfers
            ]

            session.close()
            return result

        except Exception as e:
            logger.error("Error obteniendo transferencias: %s", e)
            return []

    def assign_transfer(self, transfer_id: str, operator_username: str) -> bool:
        """
        Asigna una transferencia a un operador humano
        """
        if not self.enabled or get_session is None:
            return False

        try:
            session = get_session()

            transfer = session.query(SilentTransfer).filter(SilentTransfer.transfer_id == transfer_id).first()

            if not transfer:
                logger.error("Transferencia %s no encontrada", transfer_id)
                return False

            transfer.status = TransferStatus.IN_PROGRESS.value
            transfer.assigned_to = operator_username
            transfer.assigned_at = datetime.now(timezone.utc)

            session.commit()
            session.close()

            logger.info("✅ Transferencia %s asignada a %s", transfer_id, operator_username)
            return True

        except Exception as e:
            logger.error("Error asignando transferencia: %s", e)
            return False

    def complete_transfer(self, transfer_id: str, notes: str = None, resolution: str = None) -> bool:
        """
        Marca una transferencia como completada
        """
        if not self.enabled or get_session is None:
            return False

        try:
            session = get_session()

            transfer = session.query(SilentTransfer).filter(SilentTransfer.transfer_id == transfer_id).first()

            if not transfer:
                return False

            transfer.status = TransferStatus.COMPLETED.value
            transfer.completed_at = datetime.now(timezone.utc)

            if notes:
                transfer.notes = notes

            if resolution:
                metadata = transfer.transfer_metadata or {}
                metadata["resolution"] = resolution
                transfer.transfer_metadata = metadata

            session.commit()
            session.close()

            logger.info("✅ Transferencia %s completada", transfer_id)
            return True

        except Exception as e:
            logger.error("Error completando transferencia: %s", e)
            return False

    def get_transfer_stats(self) -> dict[str, Any]:
        """
        Estadísticas de transferencias
        """
        if not self.enabled or get_session is None:
            return {}

        try:
            session = get_session()
            dialect_name = (session.bind.dialect.name if session.bind else "").lower()

            # Total por estado
            stats = {}
            for status in TransferStatus:
                count = session.query(func.count(SilentTransfer.id)).filter(SilentTransfer.status == status.value).scalar()
                stats[f"total_{status.value}"] = count

            # Por razón (últimas 24h)
            from datetime import timedelta, timezone

            yesterday = datetime.now(timezone.utc) - timedelta(days=1)

            recent = (
                session.query(SilentTransfer.reason, func.count(SilentTransfer.id))
                .filter(SilentTransfer.created_at >= yesterday)
                .group_by(SilentTransfer.reason)
                .all()
            )

            stats["by_reason_24h"] = {reason: count for reason, count in recent}

            # Tiempo promedio de atención (cross-dialect)
            if dialect_name.startswith("postgres"):
                avg_minutes_expr = (
                    func.extract("epoch", SilentTransfer.completed_at) - func.extract("epoch", SilentTransfer.created_at)
                ) / 60.0
            else:
                # SQLite fallback
                avg_minutes_expr = (
                    func.julianday(SilentTransfer.completed_at) - func.julianday(SilentTransfer.created_at)
                ) * 24 * 60

            avg_time = (
                session.query(func.avg(avg_minutes_expr))
                .filter(SilentTransfer.status == TransferStatus.COMPLETED.value, SilentTransfer.completed_at.isnot(None))
                .scalar()
            )

            stats["avg_response_time_minutes"] = round(avg_time, 2) if avg_time else 0

            # Cadena de chats pendientes (string_agg para PostgreSQL, group_concat para SQLite)
            if dialect_name.startswith("postgres"):
                pending_chat_ids_csv = (
                    session.query(func.string_agg(cast(SilentTransfer.chat_id, String), ","))
                    .filter(SilentTransfer.status == TransferStatus.PENDING.value)
                    .scalar()
                )
            else:
                pending_chat_ids_csv = (
                    session.query(func.group_concat(cast(SilentTransfer.chat_id, String), ","))
                    .filter(SilentTransfer.status == TransferStatus.PENDING.value)
                    .scalar()
                )

            stats["pending_chat_ids_csv"] = pending_chat_ids_csv or ""

            session.close()
            return stats

        except Exception as e:
            logger.error("Error obteniendo estadísticas: %s", e)
            return {}


# Instancia global
silent_transfer_manager = SilentTransferManager()
