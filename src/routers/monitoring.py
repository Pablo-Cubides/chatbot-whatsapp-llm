"""
Monitoring API Router — Audit logs & Alert management.
Extracted from admin_panel.py.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.routers.deps import (
    alert_manager,
    audit_manager,
    get_current_user,
    require_admin,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["monitoring"])


# ═══════════════════════ Audit ═══════════════════════


@router.get("/api/audit/logs")
async def get_audit_logs(
    username: Optional[str] = None,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Obtener logs de auditoría (solo admin)"""
    try:
        logs = audit_manager.get_logs(
            username=username,
            action=action,
            resource=resource,
            limit=limit,
            offset=offset,
        )
        return {"logs": logs, "count": len(logs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/audit/stats")
async def get_audit_stats(
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Obtener estadísticas de auditoría (solo admin)"""
    try:
        stats = audit_manager.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════ Alerts ═══════════════════════


@router.get("/api/alerts")
async def get_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    chat_id: Optional[str] = None,
    assigned_to: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Obtener alertas con filtros"""
    try:
        alerts = alert_manager.get_alerts(
            status=status,
            severity=severity,
            chat_id=chat_id,
            assigned_to=assigned_to,
            limit=limit,
            offset=offset,
        )
        return {"alerts": alerts, "count": len(alerts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/alerts/{alert_id}/assign")
async def assign_alert(
    alert_id: str,
    assigned_to: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Asignar una alerta a un operador"""
    try:
        success = alert_manager.assign_alert(alert_id, assigned_to)
        if not success:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")
        return {"success": True, "message": f"Alerta asignada a {assigned_to}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    notes: Optional[str] = None,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Resolver una alerta"""
    try:
        success = alert_manager.resolve_alert(alert_id, notes)
        if not success:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")
        return {"success": True, "message": "Alerta resuelta"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/alert-rules")
async def get_alert_rules(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Obtener todas las reglas de alerta"""
    try:
        rules = alert_manager.get_rules()
        return {"rules": rules, "count": len(rules)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AlertRuleCreate(BaseModel):
    name: str
    rule_type: str
    pattern: str
    severity: str
    actions: list[str]
    enabled: Optional[bool] = True
    schedule: Optional[dict] = None
    metadata: Optional[dict] = None


@router.post("/api/alert-rules")
async def create_alert_rule(
    rule: AlertRuleCreate,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Crear una regla de alerta (solo admin)"""
    try:
        rule_id = alert_manager.create_rule(
            name=rule.name,
            rule_type=rule.rule_type,
            pattern=rule.pattern,
            severity=rule.severity,
            actions=rule.actions,
            created_by=current_user.get("username", "unknown"),
            enabled=rule.enabled,
            schedule=rule.schedule,
            metadata=rule.metadata,
        )

        if not rule_id:
            raise HTTPException(status_code=500, detail="Error creando regla")

        return {"success": True, "rule_id": rule_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/alert-rules/{rule_id}")
async def update_alert_rule(
    rule_id: int,
    updates: dict[str, Any],
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Actualizar una regla de alerta (solo admin)"""
    try:
        success = alert_manager.update_rule(rule_id, **updates)
        if not success:
            raise HTTPException(status_code=404, detail="Regla no encontrada")
        return {"success": True, "message": "Regla actualizada"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/alert-rules/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    current_user: dict[str, Any] = Depends(require_admin),
):
    """Eliminar una regla de alerta (solo admin)"""
    try:
        success = alert_manager.delete_rule(rule_id)
        if not success:
            raise HTTPException(status_code=404, detail="Regla no encontrada")
        return {"success": True, "message": "Regla eliminada"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
