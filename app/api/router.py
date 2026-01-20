"""
🔀 Router Principal de la API
Combina todos los routers de endpoints en uno principal.
"""

from fastapi import APIRouter
from app.api.endpoints import auth, business_config, queue, alerts, analytics, whatsapp, health

# Router principal que agrupa todos los subrouters
api_router = APIRouter()

# Incluir routers de cada módulo
api_router.include_router(health.router)  # Health checks primero
api_router.include_router(auth.router)
api_router.include_router(business_config.router)
api_router.include_router(queue.router)
api_router.include_router(queue.campaigns_router)
api_router.include_router(alerts.router)
api_router.include_router(alerts.rules_router)
api_router.include_router(analytics.router)
api_router.include_router(whatsapp.router)


def get_api_router() -> APIRouter:
    """Retorna el router principal de la API."""
    return api_router
