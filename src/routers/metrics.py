"""Prometheus and JSON metrics router.

Router location under src/routers aligns observability API ownership with the
rest of HTTP endpoints while reusing the metrics registry from services layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from src.services.metrics import get_metrics_snapshot
from src.services.metrics import _prometheus_text as prometheus_text  # intentional shared formatter

router = APIRouter(tags=["monitoring"])


@router.get("/metrics")
async def metrics_endpoint() -> Response:
    """Prometheus-compatible /metrics endpoint."""
    body = prometheus_text()
    return Response(
        content=body,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/metrics/json")
async def metrics_json() -> dict:
    """JSON metrics endpoint for dashboards."""
    return get_metrics_snapshot()
