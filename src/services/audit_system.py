"""
🔍 Sistema de Auditoría
Registro de acciones administrativas para trazabilidad y seguridad
"""

import logging
import os
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from src.models.admin_db import get_session
from src.models.models import Base

logger = logging.getLogger(__name__)


class AuditLog(Base):
    """Modelo de log de auditoría"""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    username = Column(String(100), nullable=False, index=True)
    role = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False, index=True)
    resource = Column(String(200), nullable=True, index=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    success = Column(String(10), default="success", nullable=False)
    error_message = Column(Text, nullable=True)


class AuditManager:
    """Gestor de auditoría"""

    def __init__(self):
        self.enabled = os.environ.get("AUDIT_ENABLED", "true").lower() == "true"
        if self.enabled:
            logger.info("🔍 Sistema de auditoría habilitado")

    def log_action(
        self,
        username: str,
        action: str,
        role: str = "unknown",
        resource: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Registrar una acción administrativa

        Args:
            username: Usuario que realiza la acción
            action: Tipo de acción (LOGIN, LOGOUT, BULK_SEND, CONFIG_CHANGE, etc.)
            role: Rol del usuario
            resource: Recurso afectado (opcional)
            details: Detalles adicionales en formato dict (opcional)
            ip_address: IP del cliente (opcional)
            user_agent: User agent del cliente (opcional)
            success: Si la acción fue exitosa
            error_message: Mensaje de error si falló

        Returns:
            bool: True si se registró correctamente
        """
        if not self.enabled:
            return True

        try:
            session = get_session()

            audit_entry = AuditLog(
                username=username,
                role=role,
                action=action,
                resource=resource,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                success="success" if success else "failed",
                error_message=error_message,
            )

            session.add(audit_entry)
            session.commit()
            session.close()

            logger.debug(f"✅ Auditoría registrada: {username} - {action}")
            return True

        except Exception as e:
            logger.error(f"❌ Error registrando auditoría: {e}")
            try:
                session.rollback()
                session.close()
            except Exception:
                pass
            return False

    def get_logs(
        self,
        username: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Obtener logs de auditoría con filtros

        Args:
            username: Filtrar por usuario
            action: Filtrar por tipo de acción
            resource: Filtrar por recurso
            start_date: Fecha inicial
            end_date: Fecha final
            limit: Límite de resultados
            offset: Offset para paginación

        Returns:
            Lista de logs en formato dict
        """
        try:
            session = get_session()

            query = session.query(AuditLog)

            if username:
                query = query.filter(AuditLog.username == username)
            if action:
                query = query.filter(AuditLog.action == action)
            if resource:
                query = query.filter(AuditLog.resource == resource)
            if start_date:
                query = query.filter(AuditLog.timestamp >= start_date)
            if end_date:
                query = query.filter(AuditLog.timestamp <= end_date)

            query = query.order_by(AuditLog.timestamp.desc())
            query = query.limit(limit).offset(offset)

            logs = query.all()
            session.close()

            return [
                {
                    "id": log.id,
                    "timestamp": log.timestamp.isoformat(),
                    "username": log.username,
                    "role": log.role,
                    "action": log.action,
                    "resource": log.resource,
                    "details": log.details,
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "success": log.success,
                    "error_message": log.error_message,
                }
                for log in logs
            ]

        except Exception as e:
            logger.error(f"❌ Error obteniendo logs de auditoría: {e}")
            return []

    def get_stats(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> dict[str, Any]:
        """
        Obtener estadísticas de auditoría

        Returns:
            Dict con estadísticas
        """
        try:
            session = get_session()

            query = session.query(AuditLog)

            if start_date:
                query = query.filter(AuditLog.timestamp >= start_date)
            if end_date:
                query = query.filter(AuditLog.timestamp <= end_date)

            total_actions = query.count()
            failed_actions = query.filter(AuditLog.success == "failed").count()

            # Top acciones
            from sqlalchemy import func

            top_actions = (
                session.query(AuditLog.action, func.count(AuditLog.id))
                .group_by(AuditLog.action)
                .order_by(func.count(AuditLog.id).desc())
                .limit(10)
                .all()
            )

            # Top usuarios
            top_users = (
                session.query(AuditLog.username, func.count(AuditLog.id))
                .group_by(AuditLog.username)
                .order_by(func.count(AuditLog.id).desc())
                .limit(10)
                .all()
            )

            session.close()

            return {
                "total_actions": total_actions,
                "failed_actions": failed_actions,
                "success_rate": (total_actions - failed_actions) / total_actions * 100 if total_actions > 0 else 0,
                "top_actions": [{"action": a, "count": c} for a, c in top_actions],
                "top_users": [{"username": u, "count": c} for u, c in top_users],
            }

        except Exception as e:
            logger.error(f"❌ Error obteniendo estadísticas de auditoría: {e}")
            return {}


# Instancia global
audit_manager = AuditManager()


# Helper functions para facilitar el uso
def log_login(username: str, role: str, ip: Optional[str] = None, success: bool = True, error: Optional[str] = None):
    """Log de inicio de sesión"""
    audit_manager.log_action(username, "LOGIN", role=role, ip_address=ip, success=success, error_message=error)


def log_logout(username: str, role: str, ip: Optional[str] = None):
    """Log de cierre de sesión"""
    audit_manager.log_action(username, "LOGOUT", role=role, ip_address=ip)


def log_bulk_send(username: str, role: str, campaign_id: str, contact_count: int, details: Optional[dict] = None):
    """Log de envío masivo"""
    audit_manager.log_action(
        username,
        "BULK_SEND",
        role=role,
        resource=f"campaign:{campaign_id}",
        details={**(details or {}), "contact_count": contact_count},
    )


def log_config_change(username: str, role: str, config_key: str, details: Optional[dict] = None):
    """Log de cambio de configuración"""
    audit_manager.log_action(username, "CONFIG_CHANGE", role=role, resource=config_key, details=details)


def log_schedule_create(username: str, role: str, schedule_id: str, details: Optional[dict] = None):
    """Log de creación de mensaje programado"""
    audit_manager.log_action(username, "SCHEDULE_CREATE", role=role, resource=f"schedule:{schedule_id}", details=details)


def log_alert_action(username: str, role: str, alert_id: str, action: str, details: Optional[dict] = None):
    """Log de acción sobre alerta"""
    audit_manager.log_action(username, f"ALERT_{action.upper()}", role=role, resource=f"alert:{alert_id}", details=details)
