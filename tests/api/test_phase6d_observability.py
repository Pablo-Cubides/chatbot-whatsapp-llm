"""Phase 6D observability tests for deep health and metrics contracts."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.api]


def test_healthz_returns_component_breakdown(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code in (200, 503)

    payload = response.json()
    assert "status" in payload
    assert "components" in payload

    components = payload["components"]
    assert "database" in components
    assert "redis" in components
    assert "disk" in components
    assert "memory" in components


def test_metrics_endpoint_exposes_required_phase6_series(client: TestClient) -> None:
    # Generate at least one request metric sample.
    _ = client.get("/")

    response = client.get("/metrics")
    assert response.status_code == 200

    body = response.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert "llm_requests_total" in body
    assert "llm_response_time" in body
    assert "active_ws_connections" in body
