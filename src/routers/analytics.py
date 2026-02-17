"""Analytics routes extracted from admin_panel.py."""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.models.admin_db import get_session
from src.models.models import AllowedContact, AuditLog, Conversation, DailyContext, ModelConfig
from src.services.auth_system import get_current_user

try:
    from src.services.analytics_system import analytics_manager
except Exception:
    analytics_manager = None

router = APIRouter(tags=["analytics"])


@router.get("/api/analytics")
def api_analytics(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, int]:
    """Devuelve conteos básicos de modelos, contactos y contextos diarios."""
    session = get_session()
    try:
        total_models = session.query(ModelConfig).count()
        total_contacts = session.query(AllowedContact).count()
        total_daily = session.query(DailyContext).count()
        return {"models": total_models, "contacts": total_contacts, "daily_contexts": total_daily}
    finally:
        session.close()


@router.get("/api/analytics/dashboard")
def api_analytics_dashboard(hours: int = 24, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Entrega métricas agregadas de dashboard para la ventana solicitada."""
    safe_hours = max(1, min(int(hours), 168))
    if analytics_manager:
        return analytics_manager.get_dashboard_metrics(hours=safe_hours)

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=safe_hours)
    session = get_session()
    try:
        conv_rows = session.query(Conversation).filter(Conversation.timestamp >= window_start).all()
        total_conversations = len(conv_rows)
        active_chat_ids = {row.chat_id for row in conv_rows if row.chat_id}
        active_count = len(active_chat_ids)

        error_count = (
            session.query(AuditLog)
            .filter(AuditLog.timestamp >= window_start)
            .filter(AuditLog.action.ilike("%error%"))
            .count()
        )

        api_usage = session.query(ModelConfig.provider).filter(ModelConfig.active.is_(True)).all()
        usage_map: dict[str, int] = {}
        for provider, in api_usage:
            key = provider or "unknown"
            usage_map[key] = usage_map.get(key, 0) + 1

        return {
            "period_hours": safe_hours,
            "timestamp": now.isoformat(),
            "conversations": {
                "total": total_conversations,
                "active": active_count,
                "avg_messages": round(total_conversations / active_count, 2) if active_count else 0,
                "avg_duration_minutes": 0,
                "conversion_rate": 0,
            },
            "quality": {"avg_satisfaction": 0, "total_errors": error_count},
            "api_usage": [{"provider": k, "count": v} for k, v in usage_map.items()],
        }
    finally:
        session.close()


@router.get("/api/analytics/timeseries")
def api_analytics_timeseries(metric: str = "conversations", hours: int = 24, current_user: dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Entrega serie temporal por métrica (`conversations`, `api_calls`, `errors`)."""
    safe_hours = max(1, min(int(hours), 168))
    if analytics_manager:
        mapped_metric = metric if metric in {"conversations", "api_calls", "errors"} else "conversations"
        return JSONResponse(content=analytics_manager.get_time_series_data(mapped_metric, hours=safe_hours))

    now = datetime.now(timezone.utc)
    safe_metric = metric if metric in {"conversations", "api_calls", "errors"} else "conversations"
    session = get_session()
    try:
        points: list[dict[str, Any]] = []
        for offset in range(safe_hours - 1, -1, -1):
            bucket_start = now - timedelta(hours=offset)
            bucket_end = bucket_start + timedelta(hours=1)

            if safe_metric == "conversations":
                value = (
                    session.query(Conversation)
                    .filter(Conversation.timestamp >= bucket_start)
                    .filter(Conversation.timestamp < bucket_end)
                    .count()
                )
            elif safe_metric == "errors":
                value = (
                    session.query(AuditLog)
                    .filter(AuditLog.timestamp >= bucket_start)
                    .filter(AuditLog.timestamp < bucket_end)
                    .filter(AuditLog.action.ilike("%error%"))
                    .count()
                )
            else:
                value = (
                    session.query(AuditLog)
                    .filter(AuditLog.timestamp >= bucket_start)
                    .filter(AuditLog.timestamp < bucket_end)
                    .count()
                )

            points.append({"timestamp": bucket_start.isoformat(), "metric": safe_metric, "value": value})

        return JSONResponse(content=points)
    finally:
        session.close()


@router.get("/api/analytics/realtime")
def api_analytics_realtime(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Expone indicadores de actividad de los últimos 5 minutos."""
    if analytics_manager:
        return analytics_manager.get_realtime_stats()

    now = datetime.now(timezone.utc)
    last_5 = now - timedelta(minutes=5)
    session = get_session()
    try:
        new_conversations = session.query(Conversation).filter(Conversation.timestamp >= last_5).count()
        api_calls = session.query(AuditLog).filter(AuditLog.timestamp >= last_5).count()
        errors = (
            session.query(AuditLog)
            .filter(AuditLog.timestamp >= last_5)
            .filter(AuditLog.action.ilike("%error%"))
            .count()
        )
        return {
            "timestamp": now.isoformat(),
            "last_5_minutes": {"new_conversations": new_conversations, "api_calls": api_calls, "errors": errors},
        }
    finally:
        session.close()
