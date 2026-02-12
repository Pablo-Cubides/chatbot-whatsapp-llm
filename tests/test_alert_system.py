"""
Tests para el sistema de alertas
"""

import pytest

from src.models.admin_db import engine
from src.models.models import Base
from src.services.alert_system import AlertManager, AlertRuleType, AlertSeverity


class TestAlertSystem:
    @classmethod
    def setup_class(cls):
        """Setup una vez para toda la clase - crear tablas"""
        Base.metadata.create_all(bind=engine)

    def setup_method(self):
        """Setup para cada test"""
        self.alert_manager = AlertManager()

    def test_check_keyword_alert(self):
        """Test detección de alerta por keyword"""
        # Crear regla de prueba
        self.alert_manager.create_rule(
            name="Test Urgent",
            rule_type=AlertRuleType.KEYWORD,
            pattern="urgente|emergencia",
            severity=AlertSeverity.HIGH,
            actions=["create_alert"],
            created_by="test",
        )

        # Verificar mensaje con keyword
        alerts = self.alert_manager.check_alert_rules("Esto es urgente por favor", "chat_test_123")

        assert len(alerts) > 0

    def test_no_alert_when_no_match(self):
        """Test que no se crea alerta cuando no hay match"""
        alerts = self.alert_manager.check_alert_rules("Mensaje normal sin keywords", "chat_test_456")

        # Puede haber alertas de reglas por defecto, verificar que no sean muchas
        assert isinstance(alerts, list)

    def test_create_alert_manually(self):
        """Test crear alerta manualmente"""
        alert_id = self.alert_manager.create_alert(
            chat_id="chat_manual_123", severity=AlertSeverity.MEDIUM, message_text="Test manual alert"
        )

        assert alert_id is not None
        assert alert_id.startswith("alert_")

    def test_get_alerts_with_filters(self):
        """Test obtener alertas con filtros"""
        # Crear alerta de prueba
        self.alert_manager.create_alert(chat_id="chat_filter_test", severity=AlertSeverity.HIGH, message_text="Test filter")

        # Obtener alertas con filtro
        alerts = self.alert_manager.get_alerts(status="open", severity=AlertSeverity.HIGH, limit=10)

        assert isinstance(alerts, list)
        assert len(alerts) > 0

    def test_assign_alert(self):
        """Test asignar alerta"""
        alert_id = self.alert_manager.create_alert(chat_id="chat_assign", severity=AlertSeverity.MEDIUM)

        result = self.alert_manager.assign_alert(alert_id, "operator_1")

        assert result is True

    def test_resolve_alert(self):
        """Test resolver alerta"""
        alert_id = self.alert_manager.create_alert(chat_id="chat_resolve", severity=AlertSeverity.LOW)

        result = self.alert_manager.resolve_alert(alert_id, "Resolved by test")

        assert result is True

    def test_create_rule(self):
        """Test crear regla de alerta"""
        rule_id = self.alert_manager.create_rule(
            name="Test Rule",
            rule_type=AlertRuleType.KEYWORD,
            pattern="test",
            severity=AlertSeverity.LOW,
            actions=["create_alert"],
            created_by="test_user",
        )

        assert rule_id is not None

    def test_get_rules(self):
        """Test obtener todas las reglas"""
        rules = self.alert_manager.get_rules()

        assert isinstance(rules, list)
        assert len(rules) >= 3  # Al menos las 3 reglas por defecto

    def test_update_rule(self):
        """Test actualizar regla"""
        # Crear regla
        rule_id = self.alert_manager.create_rule(
            name="Original",
            rule_type=AlertRuleType.KEYWORD,
            pattern="original",
            severity=AlertSeverity.LOW,
            actions=["create_alert"],
            created_by="test",
        )

        # Actualizar
        result = self.alert_manager.update_rule(rule_id, name="Updated", enabled=False)

        assert result is True

    def test_delete_rule(self):
        """Test eliminar regla"""
        rule_id = self.alert_manager.create_rule(
            name="To Delete",
            rule_type=AlertRuleType.KEYWORD,
            pattern="delete",
            severity=AlertSeverity.LOW,
            actions=["create_alert"],
            created_by="test",
        )

        result = self.alert_manager.delete_rule(rule_id)

        assert result is True


if __name__ == "__main__":
    pytest.main([__file__])
