"""
📊 Endpoints de Health Check y Métricas
Endpoints para monitoreo, health checks y métricas Prometheus.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import os
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health & Metrics"])

# Tiempo de inicio de la aplicación
START_TIME = time.time()

# Contadores de métricas
_metrics = {
    "requests_total": 0,
    "errors_total": 0,
    "auth_success": 0,
    "auth_failures": 0,
    "messages_sent": 0,
    "messages_received": 0,
    "llm_requests": 0,
    "cache_hits": 0,
    "cache_misses": 0,
}


def increment_metric(name: str, value: int = 1):
    """Incrementa un contador de métrica."""
    if name in _metrics:
        _metrics[name] += value


def get_metrics() -> Dict[str, Any]:
    """Retorna todas las métricas actuales."""
    return _metrics.copy()


@router.get("/healthz")
async def health_check():
    """
    Health check básico.
    
    Returns 200 si el servicio está funcionando.
    """
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/health")
async def detailed_health_check():
    """
    Health check detallado con estado de dependencias.
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": int(time.time() - START_TIME),
        "checks": {}
    }
    
    # Check database
    try:
        from admin_db import get_session
        from sqlalchemy import text
        session = get_session()
        session.execute(text("SELECT 1"))
        session.close()
        health["checks"]["database"] = {"status": "healthy"}
    except Exception as e:
        health["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"
    
    # Check Redis (if configured)
    try:
        redis_url = os.environ.get("REDIS_URL")
        if redis_url:
            from src.services.cache_system import cache_manager
            if cache_manager.is_connected():
                health["checks"]["redis"] = {"status": "healthy"}
            else:
                health["checks"]["redis"] = {"status": "unhealthy", "error": "Not connected"}
        else:
            health["checks"]["redis"] = {"status": "not_configured"}
    except Exception as e:
        health["checks"]["redis"] = {"status": "unhealthy", "error": str(e)}
    
    # Check WhatsApp
    try:
        whatsapp_mode = os.environ.get("WHATSAPP_MODE", "web")
        health["checks"]["whatsapp"] = {
            "status": "configured",
            "mode": whatsapp_mode
        }
    except Exception as e:
        health["checks"]["whatsapp"] = {"status": "error", "error": str(e)}
    
    # Check LLM providers
    try:
        providers = []
        if os.environ.get("GEMINI_API_KEY"):
            providers.append("gemini")
        if os.environ.get("OPENAI_API_KEY"):
            providers.append("openai")
        if os.environ.get("ANTHROPIC_API_KEY"):
            providers.append("claude")
        if os.environ.get("XAI_API_KEY"):
            providers.append("xai")
        
        health["checks"]["llm_providers"] = {
            "status": "healthy" if providers else "no_providers",
            "configured": providers
        }
    except Exception as e:
        health["checks"]["llm_providers"] = {"status": "error", "error": str(e)}
    
    return health


@router.get("/ready")
async def readiness_check():
    """
    Readiness check para Kubernetes.
    
    Verifica que la aplicación esté lista para recibir tráfico.
    """
    try:
        # Verificar conexión a DB
        from admin_db import get_session
        from sqlalchemy import text
        session = get_session()
        session.execute(text("SELECT 1"))
        session.close()
        
        return {"ready": True}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Not ready: {str(e)}")


@router.get("/live")
async def liveness_check():
    """
    Liveness check para Kubernetes.
    
    Verifica que el proceso esté vivo.
    """
    return {"alive": True, "pid": os.getpid()}


@router.get("/metrics")
async def prometheus_metrics():
    """
    Métricas en formato Prometheus.
    """
    from fastapi.responses import PlainTextResponse
    
    uptime = int(time.time() - START_TIME)
    
    lines = [
        "# HELP app_uptime_seconds Time since application start",
        "# TYPE app_uptime_seconds gauge",
        f"app_uptime_seconds {uptime}",
        "",
        "# HELP app_requests_total Total number of requests",
        "# TYPE app_requests_total counter",
        f'app_requests_total {_metrics["requests_total"]}',
        "",
        "# HELP app_errors_total Total number of errors",
        "# TYPE app_errors_total counter",
        f'app_errors_total {_metrics["errors_total"]}',
        "",
        "# HELP app_auth_success_total Successful authentications",
        "# TYPE app_auth_success_total counter",
        f'app_auth_success_total {_metrics["auth_success"]}',
        "",
        "# HELP app_auth_failures_total Failed authentications",
        "# TYPE app_auth_failures_total counter",
        f'app_auth_failures_total {_metrics["auth_failures"]}',
        "",
        "# HELP app_messages_sent_total Messages sent",
        "# TYPE app_messages_sent_total counter",
        f'app_messages_sent_total {_metrics["messages_sent"]}',
        "",
        "# HELP app_messages_received_total Messages received",
        "# TYPE app_messages_received_total counter",
        f'app_messages_received_total {_metrics["messages_received"]}',
        "",
        "# HELP app_llm_requests_total LLM API requests",
        "# TYPE app_llm_requests_total counter",
        f'app_llm_requests_total {_metrics["llm_requests"]}',
        "",
        "# HELP app_cache_hits_total Cache hits",
        "# TYPE app_cache_hits_total counter",
        f'app_cache_hits_total {_metrics["cache_hits"]}',
        "",
        "# HELP app_cache_misses_total Cache misses",
        "# TYPE app_cache_misses_total counter",
        f'app_cache_misses_total {_metrics["cache_misses"]}',
    ]
    
    # Agregar métricas del sistema si psutil está disponible
    try:
        import psutil
        
        lines.extend([
            "",
            "# HELP process_cpu_percent Process CPU usage",
            "# TYPE process_cpu_percent gauge",
            f"process_cpu_percent {psutil.Process().cpu_percent()}",
            "",
            "# HELP process_memory_bytes Process memory usage",
            "# TYPE process_memory_bytes gauge",
            f"process_memory_bytes {psutil.Process().memory_info().rss}",
            "",
            "# HELP system_cpu_percent System CPU usage",
            "# TYPE system_cpu_percent gauge",
            f"system_cpu_percent {psutil.cpu_percent()}",
            "",
            "# HELP system_memory_percent System memory usage",
            "# TYPE system_memory_percent gauge",
            f"system_memory_percent {psutil.virtual_memory().percent}",
        ])
    except ImportError:
        pass
    
    return PlainTextResponse("\n".join(lines), media_type="text/plain")


@router.get("/info")
async def app_info():
    """
    Información de la aplicación.
    """
    return {
        "name": "WhatsApp AI Chatbot",
        "version": "3.0.0",
        "python_version": os.popen("python --version").read().strip(),
        "environment": "development" if os.environ.get("DEBUG") else "production",
        "uptime_seconds": int(time.time() - START_TIME),
        "features": {
            "whatsapp_mode": os.environ.get("WHATSAPP_MODE", "web"),
            "redis_enabled": bool(os.environ.get("REDIS_URL")),
            "legacy_auth_enabled": os.environ.get("LEGACY_TOKEN_ENABLED", "false") == "true",
            "audit_enabled": os.environ.get("AUDIT_ENABLED", "true") == "true",
            "alerts_enabled": os.environ.get("ALERTS_ENABLED", "true") == "true",
        }
    }
