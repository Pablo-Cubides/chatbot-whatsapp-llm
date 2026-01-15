"""
🔇 Sistema de Transferencia Silenciosa a Humano
Transfiere conversaciones a humanos SIN que el cliente se entere
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean
from sqlalchemy.orm import Session

try:
    from src.models.models import Base
    from src.models.admin_db import get_session
except ImportError:
    # Fallback para desarrollo
    Base = None
    get_session = None

logger = logging.getLogger(__name__)


class TransferReason(Enum):
    """Razones de transferencia"""
    LLM_FAILURE = "llm_failure"              # Todos los LLM fallaron
    SIMPLE_QUESTION_FAIL = "simple_fail"     # Pregunta simple falló
    ETHICAL_REFUSAL = "ethical_refusal"      # LLM se negó por ética
    HIGH_VALUE_CLIENT = "high_value"         # Cliente de alto valor
    EXPLICIT_REQUEST = "explicit_request"    # Cliente pidió humano
    SUSPICION_DETECTED = "suspicion"         # Cliente sospechó bot
    NEGATIVE_EMOTION = "negative_emotion"    # Emoción muy negativa
    CRITICAL_ERROR = "critical_error"        # Error crítico del sistema


class TransferStatus(Enum):
    """Estados de transferencia"""
    PENDING = "pending"           # Esperando atención humana
    IN_PROGRESS = "in_progress"   # Humano atendiendo
    COMPLETED = "completed"       # Atención completada
    CANCELLED = "cancelled"       # Cancelada (cliente se fue)


if Base is not None:
    class SilentTransfer(Base):
        """Modelo de transferencias silenciosas"""
        __tablename__ = "silent_transfers"
        
        id = Column(Integer, primary_key=True, autoincrement=True)
        transfer_id = Column(String(100), unique=True, nullable=False, index=True)
        chat_id = Column(String(200), nullable=False, index=True)
        
        # Razón y contexto
        reason = Column(String(50), nullable=False, index=True)
        trigger_message = Column(Text, nullable=True)  # Mensaje que causó la transferencia
        conversation_context = Column(JSON, nullable=True)  # Últimos mensajes
        
        # Estado
        status = Column(String(20), default=TransferStatus.PENDING.value, nullable=False, index=True)
        priority = Column(Integer, default=5, nullable=False)  # 1-10, 10 = máxima urgencia
        
        # Tiempos
        created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
        assigned_at = Column(DateTime, nullable=True)
        completed_at = Column(DateTime, nullable=True)
        
        # Asignación
        assigned_to = Column(String(100), nullable=True, index=True)
        
        # Metadata
        metadata = Column(JSON, nullable=True)
        notes = Column(Text, nullable=True)
        
        # Cliente sabe que fue transferido?
        client_notified = Column(Boolean, default=False, nullable=False)


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
            TransferReason.SUSPICION_DETECTED: 10,      # Máxima urgencia
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
        conversation_history: List[Dict] = None,
        context: Dict[str, Any] = None
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
        conversation_history: List[Dict] = None,
        metadata: Dict[str, Any] = None,
        notify_client: bool = False
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
            transfer_id = f"transfer_{chat_id}_{int(datetime.utcnow().timestamp())}"
            
            # Determinar prioridad
            priority = self.priority_map.get(reason, 5)
            
            # Extraer contexto relevante
            context_data = {
                "last_messages": conversation_history[-10:] if conversation_history else [],
                "transfer_reason": reason.value,
                "timestamp": datetime.utcnow().isoformat(),
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
                metadata=metadata,
            )
            
            session.add(transfer)
            session.commit()
            
            logger.warning(f"🔇 TRANSFERENCIA SILENCIOSA creada: {transfer_id}")
            logger.warning(f"   Razón: {reason.value}")
            logger.warning(f"   Chat: {chat_id}")
            logger.warning(f"   Mensaje: {trigger_message[:100]}")
            logger.warning(f"   Cliente notificado: {notify_client}")
            
            # Notificar a operadores humanos
            if not notify_client:
                self._notify_operators_silent(transfer_id, chat_id, reason, trigger_message)
            else:
                self._notify_operators_explicit(transfer_id, chat_id, reason)
            
            session.close()
            return transfer_id
            
        except Exception as e:
            logger.error(f"❌ Error creando transferencia silenciosa: {e}")
            try:
                session.rollback()
                session.close()
            except:
                pass
            return None
    
    def _notify_operators_silent(
        self,
        transfer_id: str,
        chat_id: str,
        reason: TransferReason,
        trigger_message: str
    ):
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
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Log para operadores
        logger.warning("=" * 80)
        logger.warning("🚨 ALERTA DE TRANSFERENCIA SILENCIOSA")
        logger.warning("=" * 80)
        logger.warning(f"Transfer ID: {transfer_id}")
        logger.warning(f"Chat ID: {chat_id}")
        logger.warning(f"Razón: {reason.value}")
        logger.warning(f"Mensaje: {trigger_message}")
        logger.warning("")
        logger.warning("INSTRUCCIONES PARA OPERADOR HUMANO:")
        for instruction in notification["instructions"]:
            logger.warning(f"  {instruction}")
        logger.warning("=" * 80)
        
        # TODO: Enviar a webhook/sistema de notificaciones
        if self.notification_webhook:
            try:
                import requests
                requests.post(
                    self.notification_webhook,
                    json=notification,
                    timeout=5
                )
            except Exception as e:
                logger.error(f"Error enviando notificación: {e}")
    
    def _notify_operators_explicit(
        self,
        transfer_id: str,
        chat_id: str,
        reason: TransferReason
    ):
        """
        Notifica transferencia EXPLÍCITA (cliente pidió hablar con humano)
        """
        logger.info(f"📞 Transferencia explícita: {transfer_id} - {chat_id}")
        # Notificación normal
    
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
    
    def get_pending_transfers(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Obtiene transferencias pendientes para atención
        
        Returns:
            Lista de transferencias ordenadas por prioridad
        """
        if not self.enabled or get_session is None:
            return []
        
        try:
            session = get_session()
            
            transfers = session.query(SilentTransfer).filter(
                SilentTransfer.status == TransferStatus.PENDING.value
            ).order_by(
                SilentTransfer.priority.desc(),
                SilentTransfer.created_at.asc()
            ).limit(limit).all()
            
            result = [
                {
                    "transfer_id": t.transfer_id,
                    "chat_id": t.chat_id,
                    "reason": t.reason,
                    "priority": t.priority,
                    "trigger_message": t.trigger_message,
                    "created_at": t.created_at.isoformat(),
                    "silent": not t.client_notified,
                    "waiting_time_minutes": (datetime.utcnow() - t.created_at).total_seconds() / 60,
                }
                for t in transfers
            ]
            
            session.close()
            return result
            
        except Exception as e:
            logger.error(f"Error obteniendo transferencias: {e}")
            return []
    
    def assign_transfer(self, transfer_id: str, operator_username: str) -> bool:
        """
        Asigna una transferencia a un operador humano
        """
        if not self.enabled or get_session is None:
            return False
        
        try:
            session = get_session()
            
            transfer = session.query(SilentTransfer).filter(
                SilentTransfer.transfer_id == transfer_id
            ).first()
            
            if not transfer:
                logger.error(f"Transferencia {transfer_id} no encontrada")
                return False
            
            transfer.status = TransferStatus.IN_PROGRESS.value
            transfer.assigned_to = operator_username
            transfer.assigned_at = datetime.utcnow()
            
            session.commit()
            session.close()
            
            logger.info(f"✅ Transferencia {transfer_id} asignada a {operator_username}")
            return True
            
        except Exception as e:
            logger.error(f"Error asignando transferencia: {e}")
            return False
    
    def complete_transfer(
        self,
        transfer_id: str,
        notes: str = None,
        resolution: str = None
    ) -> bool:
        """
        Marca una transferencia como completada
        """
        if not self.enabled or get_session is None:
            return False
        
        try:
            session = get_session()
            
            transfer = session.query(SilentTransfer).filter(
                SilentTransfer.transfer_id == transfer_id
            ).first()
            
            if not transfer:
                return False
            
            transfer.status = TransferStatus.COMPLETED.value
            transfer.completed_at = datetime.utcnow()
            
            if notes:
                transfer.notes = notes
            
            if resolution:
                metadata = transfer.metadata or {}
                metadata["resolution"] = resolution
                transfer.metadata = metadata
            
            session.commit()
            session.close()
            
            logger.info(f"✅ Transferencia {transfer_id} completada")
            return True
            
        except Exception as e:
            logger.error(f"Error completando transferencia: {e}")
            return False
    
    def get_transfer_stats(self) -> Dict[str, Any]:
        """
        Estadísticas de transferencias
        """
        if not self.enabled or get_session is None:
            return {}
        
        try:
            session = get_session()
            
            from sqlalchemy import func
            
            # Total por estado
            stats = {}
            for status in TransferStatus:
                count = session.query(func.count(SilentTransfer.id)).filter(
                    SilentTransfer.status == status.value
                ).scalar()
                stats[f"total_{status.value}"] = count
            
            # Por razón (últimas 24h)
            from datetime import timedelta
            yesterday = datetime.utcnow() - timedelta(days=1)
            
            recent = session.query(
                SilentTransfer.reason,
                func.count(SilentTransfer.id)
            ).filter(
                SilentTransfer.created_at >= yesterday
            ).group_by(SilentTransfer.reason).all()
            
            stats["by_reason_24h"] = {reason: count for reason, count in recent}
            
            # Tiempo promedio de atención
            avg_time = session.query(
                func.avg(
                    func.julianday(SilentTransfer.completed_at) - 
                    func.julianday(SilentTransfer.created_at)
                ) * 24 * 60  # Convertir a minutos
            ).filter(
                SilentTransfer.status == TransferStatus.COMPLETED.value,
                SilentTransfer.completed_at.isnot(None)
            ).scalar()
            
            stats["avg_response_time_minutes"] = round(avg_time, 2) if avg_time else 0
            
            session.close()
            return stats
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {}


# Instancia global
silent_transfer_manager = SilentTransferManager()
