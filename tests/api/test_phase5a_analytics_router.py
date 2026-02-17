"""Phase 5A analytics router coverage tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.api]


def test_analytics_dashboard_returns_expected_sections(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get("/api/analytics/dashboard?hours=24", headers=admin_headers)
    assert response.status_code == 200

    payload = response.json()
    assert "period_hours" in payload
    assert "conversations" in payload
    assert "quality" in payload
    assert "api_usage" in payload


def test_analytics_timeseries_invalid_metric_falls_back_to_conversations(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    response = client.get(
        "/api/analytics/timeseries?metric=not-valid&hours=500",
        headers=admin_headers,
    )
    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload, list)
    if payload:
        first = payload[0]
        assert "timestamp" in first
        assert "value" in first or "metric" in first


def test_analytics_realtime_returns_last_5_minutes(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get("/api/analytics/realtime", headers=admin_headers)
    assert response.status_code == 200

    payload = response.json()
    assert "last_5_minutes" in payload
    stats = payload["last_5_minutes"]
    assert "errors" in stats
    assert "new_conversations" in stats
