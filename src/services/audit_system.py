"""
🔍 Sistema de Auditoría
Registro de acciones administrativas para trazabilidad y seguridad
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy import delete
from sqlalchemy import and_, or_
from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from src.models.admin_db import get_session
from src.models.models import Base

logger = logging.getLogger(__name__)

SENSITIVE_DETAIL_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "secret",
    "api_key",
}


def _sanitize_details(payload: Any) -> Any:
    """Redact potentially sensitive values before persisting telemetry."""
    if isinstance(payload, dict):
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            key_lower = str(key).lower()
            if key_lower in SENSITIVE_DETAIL_KEYS or key_lower.endswith("_token") or key_lower.endswith("_secret"):
                sanitized[str(key)] = "[REDACTED]"
            else:
                sanitized[str(key)] = _sanitize_details(value)
        return sanitized
    if isinstance(payload, list):
        return [_sanitize_details(item) for item in payload]
    return payload


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    """Modelo de log de auditoría"""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=_utcnow, nullable=False, index=True)
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
                details=_sanitize_details(details or {}),
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

    def get_security_signal_report(
        self,
        window_minutes: int = 15,
        thresholds: Optional[dict[str, int]] = None,
    ) -> dict[str, Any]:
        """Build threshold-based anomaly report from SECURITY_* audit events."""
        now = datetime.now(timezone.utc)
        window_minutes = max(1, min(window_minutes, 24 * 60))
        start_date = now - timedelta(minutes=window_minutes)

        baseline_thresholds = {
            "SECURITY_LOGIN_FAILED": int(os.environ.get("SECURITY_THRESHOLD_LOGIN_FAILED", "5")),
            "SECURITY_LOGIN_LOCKOUT": int(os.environ.get("SECURITY_THRESHOLD_LOGIN_LOCKOUT", "1")),
            "SECURITY_REFRESH_FAILED": int(os.environ.get("SECURITY_THRESHOLD_REFRESH_FAILED", "8")),
            "SECURITY_WS_UNAUTHORIZED": int(os.environ.get("SECURITY_THRESHOLD_WS_UNAUTHORIZED", "8")),
            "SECURITY_WS_INVALID_SCOPE": int(os.environ.get("SECURITY_THRESHOLD_WS_INVALID_SCOPE", "3")),
        }
        if thresholds:
            for key, value in thresholds.items():
                if key in baseline_thresholds and isinstance(value, int) and value > 0:
                    baseline_thresholds[key] = value

        try:
            session = get_session()
            rows = (
                session.query(AuditLog.action, func.count(AuditLog.id).label("count"))
                .filter(AuditLog.timestamp >= start_date)
                .filter(AuditLog.action.like("SECURITY_%"))
                .group_by(AuditLog.action)
                .all()
            )
            session.close()

            event_counts = {action: int(count) for action, count in rows}
            anomalies: list[dict[str, Any]] = []
            for event_name, threshold in baseline_thresholds.items():
                count = event_counts.get(event_name, 0)
                if count >= threshold:
                    severity = "high" if count >= threshold * 2 else "medium"
                    anomalies.append(
                        {
                            "event": event_name,
                            "count": count,
                            "threshold": threshold,
                            "severity": severity,
                        }
                    )

            return {
                "generated_at": now.isoformat(),
                "window_minutes": window_minutes,
                "totals": event_counts,
                "thresholds": baseline_thresholds,
                "anomalies": anomalies,
                "healthy": len(anomalies) == 0,
            }
        except Exception as e:
            logger.error(f"❌ Error generando reporte de señales de seguridad: {e}")
            return {
                "generated_at": now.isoformat(),
                "window_minutes": window_minutes,
                "totals": {},
                "thresholds": baseline_thresholds,
                "anomalies": [],
                "healthy": True,
            }

    def get_security_retention_preview(
        self,
        retention_days: int,
        include_protected_actions: bool = False,
    ) -> dict[str, Any]:
        """Preview how many SECURITY_* logs are eligible for retention purge."""
        safe_days = max(1, min(retention_days, 3650))
        cutoff = datetime.now(timezone.utc) - timedelta(days=safe_days)

        protected_actions = [
            action.strip()
            for action in os.environ.get(
                "SECURITY_RETENTION_PROTECTED_ACTIONS",
                "SECURITY_SNAPSHOT_VERIFICATION_PERFORMED",
            ).split(",")
            if action.strip()
        ]

        try:
            session = get_session()
            query = session.query(AuditLog).filter(AuditLog.action.like("SECURITY_%")).filter(AuditLog.timestamp < cutoff)
            if protected_actions and not include_protected_actions:
                query = query.filter(~AuditLog.action.in_(protected_actions))

            count = query.count()
            oldest = query.order_by(AuditLog.timestamp.asc()).first()
            newest = query.order_by(AuditLog.timestamp.desc()).first()
            session.close()

            return {
                "retention_days": safe_days,
                "cutoff": cutoff.isoformat(),
                "count": int(count),
                "oldest": oldest.timestamp.isoformat() if oldest else None,
                "newest": newest.timestamp.isoformat() if newest else None,
                "protected_actions": protected_actions,
                "include_protected_actions": include_protected_actions,
            }
        except Exception as e:
            logger.error(f"❌ Error generando preview de retención security: {e}")
            return {
                "retention_days": safe_days,
                "cutoff": cutoff.isoformat(),
                "count": 0,
                "oldest": None,
                "newest": None,
                "protected_actions": protected_actions,
                "include_protected_actions": include_protected_actions,
            }

    def purge_security_logs(
        self,
        retention_days: int,
        dry_run: bool = True,
        include_protected_actions: bool = False,
    ) -> dict[str, Any]:
        """Purge old SECURITY_* audit events according to retention policy."""
        preview = self.get_security_retention_preview(
            retention_days=retention_days,
            include_protected_actions=include_protected_actions,
        )

        if dry_run:
            return {
                **preview,
                "dry_run": True,
                "deleted_count": 0,
            }

        if int(preview.get("count", 0)) <= 0:
            return {
                **preview,
                "dry_run": False,
                "deleted_count": 0,
            }

        cutoff_dt = datetime.fromisoformat(str(preview["cutoff"]))
        protected_actions = list(preview.get("protected_actions") or [])

        try:
            session = get_session()
            stmt = delete(AuditLog).where(AuditLog.action.like("SECURITY_%")).where(AuditLog.timestamp < cutoff_dt)
            if protected_actions and not include_protected_actions:
                stmt = stmt.where(~AuditLog.action.in_(protected_actions))

            result = session.execute(stmt)
            session.commit()
            session.close()

            return {
                **preview,
                "dry_run": False,
                "deleted_count": int(result.rowcount or 0),
            }
        except Exception as e:
            logger.error(f"❌ Error purgando security logs: {e}")
            try:
                session.rollback()
                session.close()
            except Exception:
                pass
            return {
                **preview,
                "dry_run": False,
                "deleted_count": 0,
            }

    def export_security_events_since(self, since: datetime, limit: int = 200) -> list[dict[str, Any]]:
        """Export SECURITY_* events newer than `since` in ascending timestamp order."""
        safe_limit = max(1, min(limit, 2000))
        since_utc = since if since.tzinfo else since.replace(tzinfo=timezone.utc)

        try:
            session = get_session()
            rows = (
                session.query(AuditLog)
                .filter(AuditLog.action.like("SECURITY_%"))
                .filter(AuditLog.timestamp > since_utc)
                .order_by(AuditLog.timestamp.asc(), AuditLog.id.asc())
                .limit(safe_limit)
                .all()
            )
            session.close()

            exported: list[dict[str, Any]] = []
            for row in rows:
                exported.append(
                    {
                        "id": row.id,
                        "timestamp": row.timestamp.isoformat(),
                        "username": row.username,
                        "role": row.role,
                        "action": row.action,
                        "resource": row.resource,
                        "details": row.details,
                        "success": row.success,
                    }
                )
            return exported
        except Exception as e:
            logger.error(f"❌ Error exportando eventos SECURITY_*: {e}")
            return []

    def export_security_events_cursor(
        self,
        since: datetime,
        after_id: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Export SECURITY_* events using a stable cursor (timestamp + id)."""
        safe_limit = max(1, min(limit, 2000))
        safe_after_id = max(0, int(after_id or 0))
        since_utc = since if since.tzinfo else since.replace(tzinfo=timezone.utc)

        try:
            session = get_session()
            cursor_filter = or_(
                AuditLog.timestamp > since_utc,
                and_(AuditLog.timestamp == since_utc, AuditLog.id > safe_after_id),
            )
            rows = (
                session.query(AuditLog)
                .filter(AuditLog.action.like("SECURITY_%"))
                .filter(cursor_filter)
                .order_by(AuditLog.timestamp.asc(), AuditLog.id.asc())
                .limit(safe_limit)
                .all()
            )
            session.close()

            exported: list[dict[str, Any]] = []
            for row in rows:
                exported.append(
                    {
                        "id": row.id,
                        "timestamp": row.timestamp.isoformat(),
                        "username": row.username,
                        "role": row.role,
                        "action": row.action,
                        "resource": row.resource,
                        "details": row.details,
                        "success": row.success,
                    }
                )
            return exported
        except Exception as e:
            logger.error(f"❌ Error exportando eventos SECURITY_* por cursor: {e}")
            return []

    def set_security_export_checkpoint(
        self,
        consumer: str,
        since: datetime,
        after_id: int,
        updated_by: str,
        role: str = "admin",
    ) -> dict[str, Any]:
        """Persist latest export cursor checkpoint for a consumer using audit trail records."""
        normalized_consumer = (consumer or "").strip().lower()
        if not normalized_consumer:
            raise ValueError("consumer is required")

        since_utc = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
        safe_after_id = max(0, int(after_id or 0))

        self.log_action(
            username=updated_by,
            action="AUDIT_SECURITY_EXPORT_CHECKPOINT_SET",
            role=role,
            resource=f"consumer:{normalized_consumer}",
            details={
                "consumer": normalized_consumer,
                "since": since_utc.isoformat(),
                "after_id": safe_after_id,
            },
            success=True,
        )

        return {
            "consumer": normalized_consumer,
            "since": since_utc.isoformat(),
            "after_id": safe_after_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_security_export_checkpoint(self, consumer: str) -> Optional[dict[str, Any]]:
        """Get latest export checkpoint for a given consumer."""
        normalized_consumer = (consumer or "").strip().lower()
        if not normalized_consumer:
            return None

        try:
            session = get_session()
            row = (
                session.query(AuditLog)
                .filter(AuditLog.action == "AUDIT_SECURITY_EXPORT_CHECKPOINT_SET")
                .filter(AuditLog.resource == f"consumer:{normalized_consumer}")
                .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
                .first()
            )
            session.close()

            if not row:
                return None

            details = row.details or {}
            return {
                "consumer": normalized_consumer,
                "since": str(details.get("since") or row.timestamp.isoformat()),
                "after_id": int(details.get("after_id") or 0),
                "updated_at": row.timestamp.isoformat(),
                "updated_by": row.username,
            }
        except Exception as e:
            logger.error(f"❌ Error obteniendo checkpoint de export security: {e}")
            return None

    def list_security_export_checkpoints(self, limit: int = 100) -> list[dict[str, Any]]:
        """List latest checkpoints per consumer from audit trail."""
        safe_limit = max(1, min(limit, 1000))

        try:
            session = get_session()
            rows = (
                session.query(AuditLog)
                .filter(AuditLog.action == "AUDIT_SECURITY_EXPORT_CHECKPOINT_SET")
                .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
                .limit(safe_limit * 20)
                .all()
            )
            session.close()

            latest_by_consumer: dict[str, dict[str, Any]] = {}
            for row in rows:
                details = row.details or {}
                consumer = str(details.get("consumer") or "").strip().lower()
                if not consumer or consumer in latest_by_consumer:
                    continue
                latest_by_consumer[consumer] = {
                    "consumer": consumer,
                    "since": str(details.get("since") or row.timestamp.isoformat()),
                    "after_id": int(details.get("after_id") or 0),
                    "updated_at": row.timestamp.isoformat(),
                    "updated_by": row.username,
                }

                if len(latest_by_consumer) >= safe_limit:
                    break

            items = list(latest_by_consumer.values())
            items.sort(key=lambda item: item.get("consumer", ""))
            return items
        except Exception as e:
            logger.error(f"❌ Error listando checkpoints de export security: {e}")
            return []


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


def log_security_event(
    event_type: str,
    username: str = "unknown",
    role: str = "unknown",
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = False,
    details: Optional[dict[str, Any]] = None,
    error: Optional[str] = None,
):
    """Log de evento de seguridad estructurado para detección y forense."""
    normalized_event = event_type.strip().upper().replace(" ", "_")
    action = f"SECURITY_{normalized_event}"
    payload = {
        "event_type": normalized_event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **(details or {}),
    }
    audit_manager.log_action(
        username=username,
        action=action,
        role=role,
        resource="security",
        details=payload,
        ip_address=ip,
        user_agent=user_agent,
        success=success,
        error_message=error,
    )
