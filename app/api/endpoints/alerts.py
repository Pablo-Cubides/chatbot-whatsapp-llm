"""
🚨 Endpoints de Alertas
Gestión de alertas, reglas de alerta y notificaciones.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from src.services.auth_system import get_current_user, require_admin
from src.services.alert_system import alert_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


class CreateAlertRuleRequest(BaseModel):
    name: str
    rule_type: str  # keyword, regex, sentiment
    pattern: str
    severity: str = "medium"  # low, medium, high
    enabled: bool = True
    metadata: Optional[Dict[str, Any]] = None


class AssignAlertRequest(BaseModel):
    assigned_to: str


class ResolveAlertRequest(BaseModel):
    notes: Optional[str] = None


@router.get("/")
async def list_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """
    Lista alertas del sistema.
    
    - **status**: Filtrar por estado (open, assigned, resolved)
    - **severity**: Filtrar por severidad (low, medium, high)
    - **limit**: Cantidad máxima a retornar
    """
    try:
        alerts = alert_manager.get_alerts(
            status=status,
            severity=severity,
            limit=limit
        )
        return {
            "status": "success",
            "count": len(alerts),
            "alerts": alerts
        }
    except Exception as e:
        logger.error(f"Error listing alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_alert_stats(current_user: dict = Depends(get_current_user)):
    """
    Obtiene estadísticas de alertas.
    """
    try:
        stats = alert_manager.get_stats()
        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error getting alert stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{alert_id}")
async def get_alert(
    alert_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Obtiene detalles de una alerta específica.
    """
    try:
        alert = alert_manager.get_alert(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")
        
        return {
            "status": "success",
            "alert": alert
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{alert_id}/assign")
async def assign_alert(
    alert_id: str,
    request: AssignAlertRequest,
    current_user: dict = Depends(require_admin)
):
    """
    Asigna una alerta a un usuario.
    """
    try:
        success = alert_manager.assign_alert(alert_id, request.assigned_to)
        if not success:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")
        
        return {
            "status": "success",
            "message": f"Alerta asignada a {request.assigned_to}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    request: ResolveAlertRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Resuelve una alerta.
    """
    try:
        username = current_user.get("username", "unknown")
        success = alert_manager.resolve_alert(
            alert_id,
            resolved_by=username,
            notes=request.notes
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")
        
        return {
            "status": "success",
            "message": "Alerta resuelta"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================
# Reglas de Alerta
# =====================================

rules_router = APIRouter(prefix="/api/alert-rules", tags=["Alert Rules"])


@rules_router.get("/")
async def list_alert_rules(current_user: dict = Depends(get_current_user)):
    """
    Lista todas las reglas de alerta.
    """
    try:
        rules = alert_manager.get_rules()
        return {
            "status": "success",
            "count": len(rules),
            "rules": rules
        }
    except Exception as e:
        logger.error(f"Error listing alert rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rules_router.post("/")
async def create_alert_rule(
    request: CreateAlertRuleRequest,
    current_user: dict = Depends(require_admin)
):
    """
    Crea una nueva regla de alerta.
    
    - **name**: Nombre descriptivo de la regla
    - **rule_type**: Tipo (keyword, regex, sentiment)
    - **pattern**: Patrón a detectar
    - **severity**: Severidad de las alertas generadas
    """
    try:
        rule = alert_manager.create_rule(
            name=request.name,
            rule_type=request.rule_type,
            pattern=request.pattern,
            severity=request.severity,
            enabled=request.enabled,
            metadata=request.metadata
        )
        
        return {
            "status": "success",
            "rule": rule
        }
    except Exception as e:
        logger.error(f"Error creating alert rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rules_router.put("/{rule_id}")
async def update_alert_rule(
    rule_id: str,
    request: CreateAlertRuleRequest,
    current_user: dict = Depends(require_admin)
):
    """
    Actualiza una regla de alerta existente.
    """
    try:
        success = alert_manager.update_rule(
            rule_id,
            name=request.name,
            pattern=request.pattern,
            severity=request.severity,
            enabled=request.enabled
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Regla no encontrada")
        
        return {
            "status": "success",
            "message": "Regla actualizada"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating alert rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rules_router.delete("/{rule_id}")
async def delete_alert_rule(
    rule_id: str,
    current_user: dict = Depends(require_admin)
):
    """
    Elimina una regla de alerta.
    """
    try:
        success = alert_manager.delete_rule(rule_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Regla no encontrada")
        
        return {
            "status": "success",
            "message": "Regla eliminada"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting alert rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rules_router.post("/{rule_id}/toggle")
async def toggle_alert_rule(
    rule_id: str,
    current_user: dict = Depends(require_admin)
):
    """
    Activa/desactiva una regla de alerta.
    """
    try:
        success = alert_manager.toggle_rule(rule_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Regla no encontrada")
        
        return {
            "status": "success",
            "message": "Estado de regla cambiado"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling alert rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))
