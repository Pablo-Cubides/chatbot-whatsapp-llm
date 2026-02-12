"""
🚨 Sistema de Alertas y Handoff Humano
Detección inteligente de situaciones que requieren intervención humana
"""

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text

from src.models.admin_db import get_session
from src.models.models import Base

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Severidad de alertas"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AlertRuleType(str, Enum):
    """Tipos de reglas de alerta"""

    KEYWORD = "keyword"
    REGEX = "regex"
    SENTIMENT = "sentiment"
    NO_RESPONSE = "no_response"
    CUSTOM = "custom"


class AlertRule(Base):
    """Modelo de regla de alerta"""

    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    rule_type = Column(String(50), nullable=False, index=True)
    pattern = Column(Text, nullable=True)  # keyword, regex pattern
    severity = Column(String(20), default=AlertSeverity.MEDIUM, nullable=False)
    actions = Column(JSON, nullable=False)  # ['create_alert', 'mark_human_needed', 'notify_webhook']
    schedule = Column(JSON, nullable=True)  # horario activo
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(String(100), nullable=False)


class Alert(Base):
    """Modelo de alerta"""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(String(100), unique=True, nullable=False, index=True)
    rule_id = Column(Integer, nullable=True, index=True)
    chat_id = Column(String(200), nullable=False, index=True)
    message_text = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, index=True)
    status = Column(String(20), default="open", nullable=False, index=True)  # open, assigned, resolved
    assigned_to = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    extra_data = Column(JSON, nullable=True)


class AlertManager:
    """Gestor del sistema de alertas"""

    def __init__(self):
        self.enabled = os.environ.get("ALERTS_ENABLED", "true").lower() == "true"
        if self.enabled:
            logger.info("🚨 Sistema de alertas habilitado")
            self._load_default_rules()

    def _load_default_rules(self):
        """Cargar reglas por defecto si no existen"""
        try:
            session = get_session()

            count = session.query(AlertRule).count()

            if count == 0:
                # Crear reglas por defecto
                default_rules = [
                    {
                        "name": "Palabras urgentes",
                        "rule_type": AlertRuleType.KEYWORD,
                        "pattern": "urgente|emergencia|ayuda|problema grave|no funciona",
                        "severity": AlertSeverity.HIGH,
                        "actions": ["create_alert", "mark_human_needed"],
                        "created_by": "system",
                    },
                    {
                        "name": "Quejas o insatisfacción",
                        "rule_type": AlertRuleType.KEYWORD,
                        "pattern": "queja|insatisfecho|mal servicio|cancelar|reembolso",
                        "severity": AlertSeverity.MEDIUM,
                        "actions": ["create_alert"],
                        "created_by": "system",
                    },
                    {
                        "name": "Palabras de alto valor",
                        "rule_type": AlertRuleType.KEYWORD,
                        "pattern": "comprar|presupuesto|cotización|contratar|inversión grande",
                        "severity": AlertSeverity.HIGH,
                        "actions": ["create_alert", "notify_webhook"],
                        "created_by": "system",
                    },
                ]

                for rule_data in default_rules:
                    rule = AlertRule(**rule_data)
                    session.add(rule)

                session.commit()
                logger.info("✅ Reglas de alerta por defecto creadas")

            session.close()

        except Exception as e:
            logger.error(f"❌ Error cargando reglas por defecto: {e}")

    def check_alert_rules(self, message_text: str, chat_id: str, metadata: Optional[dict] = None) -> list[str]:
        """
        Verificar si un mensaje activa alguna regla de alerta

        Args:
            message_text: Texto del mensaje
            chat_id: ID del chat
            metadata: Metadata adicional

        Returns:
            Lista de alert_ids creados
        """
        if not self.enabled:
            return []

        try:
            session = get_session()

            # Obtener reglas activas
            rules = session.query(AlertRule).filter(AlertRule.enabled).all()

            alert_ids = []
            message_lower = message_text.lower()

            for rule in rules:
                matched = False

                if rule.rule_type == AlertRuleType.KEYWORD:
                    # Buscar keywords
                    keywords = [k.strip() for k in rule.pattern.split("|")]
                    matched = any(keyword.lower() in message_lower for keyword in keywords)

                elif rule.rule_type == AlertRuleType.REGEX:
                    # Buscar regex (con protección contra ReDoS)
                    try:
                        pattern = re.compile(rule.pattern, re.IGNORECASE)
                        # Limit regex search to first 5000 chars to prevent ReDoS
                        matched = pattern.search(message_text[:5000]) is not None
                    except re.error as regex_err:
                        logger.warning(f"⚠️ Regex inválido en regla {rule.id}: {rule.pattern} - {regex_err}")

                if matched:
                    # Crear alerta
                    alert_id = self.create_alert(
                        rule_id=rule.id,
                        chat_id=chat_id,
                        message_text=message_text,
                        severity=rule.severity,
                        metadata={**(metadata or {}), "rule_name": rule.name, "matched_pattern": rule.pattern},
                    )

                    if alert_id:
                        alert_ids.append(alert_id)
                        logger.info(f"🚨 Alerta creada: {alert_id} (regla: {rule.name})")

                        # Ejecutar acciones
                        if "mark_human_needed" in rule.actions:
                            self._mark_conversation_human_needed(chat_id)

                        if "notify_webhook" in rule.actions:
                            self._notify_webhook(alert_id, chat_id, message_text)

            session.close()
            return alert_ids

        except Exception as e:
            logger.error(f"❌ Error verificando reglas de alerta: {e}")
            return []

    def create_alert(
        self,
        chat_id: str,
        severity: str,
        rule_id: Optional[int] = None,
        message_text: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        """Crear una alerta"""
        try:
            session = get_session()

            alert_id = f"alert_{uuid.uuid4().hex[:16]}"

            alert = Alert(
                alert_id=alert_id,
                rule_id=rule_id,
                chat_id=chat_id,
                message_text=message_text,
                severity=severity,
                status="open",
                extra_data=metadata or {},
            )

            session.add(alert)
            session.commit()
            session.close()

            return alert_id

        except Exception as e:
            logger.error(f"❌ Error creando alerta: {e}")
            return None

    def get_alerts(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        chat_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Obtener alertas con filtros"""
        try:
            session = get_session()

            query = session.query(Alert)

            if status:
                query = query.filter(Alert.status == status)
            if severity:
                query = query.filter(Alert.severity == severity)
            if chat_id:
                query = query.filter(Alert.chat_id == chat_id)
            if assigned_to:
                query = query.filter(Alert.assigned_to == assigned_to)

            query = query.order_by(Alert.created_at.desc())
            query = query.limit(limit).offset(offset)

            alerts = query.all()
            session.close()

            return [self._alert_to_dict(alert) for alert in alerts]

        except Exception as e:
            logger.error(f"❌ Error obteniendo alertas: {e}")
            return []

    def assign_alert(self, alert_id: str, assigned_to: str) -> bool:
        """Asignar una alerta a un operador"""
        try:
            session = get_session()

            alert = session.query(Alert).filter(Alert.alert_id == alert_id).first()

            if alert:
                alert.assigned_to = assigned_to
                alert.status = "assigned"
                session.commit()

            session.close()
            return True

        except Exception as e:
            logger.error(f"❌ Error asignando alerta: {e}")
            return False

    def resolve_alert(self, alert_id: str, notes: Optional[str] = None) -> bool:
        """Resolver una alerta"""
        try:
            session = get_session()

            alert = session.query(Alert).filter(Alert.alert_id == alert_id).first()

            if alert:
                alert.status = "resolved"
                alert.resolved_at = datetime.now(timezone.utc)
                if notes:
                    alert.notes = notes
                session.commit()

            session.close()
            return True

        except Exception as e:
            logger.error(f"❌ Error resolviendo alerta: {e}")
            return False

    def create_rule(
        self,
        name: str,
        rule_type: str,
        pattern: str,
        severity: str,
        actions: list[str],
        created_by: str,
        enabled: bool = True,
        schedule: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[int]:
        """Crear una regla de alerta"""
        try:
            session = get_session()

            rule = AlertRule(
                name=name,
                enabled=enabled,
                rule_type=rule_type,
                pattern=pattern,
                severity=severity,
                actions=actions,
                schedule=schedule,
                extra_data=metadata or {},
                created_by=created_by,
            )

            session.add(rule)
            session.commit()
            rule_id = rule.id
            session.close()

            logger.info(f"✅ Regla de alerta creada: {rule_id}")
            return rule_id

        except Exception as e:
            logger.error(f"❌ Error creando regla: {e}")
            return None

    def get_rules(self) -> list[dict[str, Any]]:
        """Obtener todas las reglas"""
        try:
            session = get_session()

            rules = session.query(AlertRule).all()
            session.close()

            return [self._rule_to_dict(rule) for rule in rules]

        except Exception as e:
            logger.error(f"❌ Error obteniendo reglas: {e}")
            return []

    def update_rule(self, rule_id: int, **kwargs) -> bool:
        """Actualizar una regla"""
        # Whitelist allowed fields to prevent attribute injection
        ALLOWED_FIELDS = {"name", "enabled", "rule_type", "pattern", "severity", "actions", "schedule", "extra_data"}
        try:
            session = get_session()

            rule = session.query(AlertRule).filter(AlertRule.id == rule_id).first()

            if rule:
                for key, value in kwargs.items():
                    if key in ALLOWED_FIELDS and hasattr(rule, key):
                        setattr(rule, key, value)
                    else:
                        logger.warning(f"⚠️ Campo no permitido en update_rule: {key}")
                session.commit()

            session.close()
            return True

        except Exception as e:
            logger.error(f"❌ Error actualizando regla: {e}")
            return False

    def delete_rule(self, rule_id: int) -> bool:
        """Eliminar una regla"""
        try:
            session = get_session()

            rule = session.query(AlertRule).filter(AlertRule.id == rule_id).first()

            if rule:
                session.delete(rule)
                session.commit()

            session.close()
            return True

        except Exception as e:
            logger.error(f"❌ Error eliminando regla: {e}")
            return False

    def _mark_conversation_human_needed(self, chat_id: str):
        """Marcar conversación como que necesita atención humana"""
        # Esto se puede integrar con el sistema de chat_sessions
        logger.info(f"🚨 Conversación {chat_id} marcada como needs_human")

    def _notify_webhook(self, alert_id: str, chat_id: str, message_text: str):
        """Notificar vía webhook"""
        webhook_url = os.environ.get("ALERT_WEBHOOK_URL")
        if webhook_url:
            try:
                import requests

                payload = {
                    "alert_id": alert_id,
                    "chat_id": chat_id,
                    "message_text": message_text[:500],  # Truncate for safety
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                response = requests.post(webhook_url, json=payload, timeout=10)
                if response.status_code < 300:
                    logger.info(f"📞 Webhook notificado para alerta {alert_id}")
                else:
                    logger.warning(f"⚠️ Webhook respondió {response.status_code} para alerta {alert_id}")
            except Exception as e:
                logger.error(f"❌ Error notificando webhook para alerta {alert_id}: {e}")

    def _alert_to_dict(self, alert: Alert) -> dict[str, Any]:
        """Convertir alerta a diccionario"""
        return {
            "alert_id": alert.alert_id,
            "rule_id": alert.rule_id,
            "chat_id": alert.chat_id,
            "message_text": alert.message_text,
            "severity": alert.severity,
            "status": alert.status,
            "assigned_to": alert.assigned_to,
            "created_at": alert.created_at.isoformat(),
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "notes": alert.notes,
            "metadata": alert.extra_data,  # Mantener 'metadata' en API por compatibilidad
        }

    def _rule_to_dict(self, rule: AlertRule) -> dict[str, Any]:
        """Convertir regla a diccionario"""
        return {
            "id": rule.id,
            "name": rule.name,
            "enabled": rule.enabled,
            "rule_type": rule.rule_type,
            "pattern": rule.pattern,
            "severity": rule.severity,
            "actions": rule.actions,
            "schedule": rule.schedule,
            "metadata": rule.extra_data,  # Mantener 'metadata' en API por compatibilidad
            "created_at": rule.created_at.isoformat(),
            "created_by": rule.created_by,
        }


# Instancia global
alert_manager = AlertManager()
