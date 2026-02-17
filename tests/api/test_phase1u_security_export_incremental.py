"""Phase 1U incremental SECURITY_* export tests for SIEM/SOC ingestion."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.models.admin_db import get_session
from src.services.audit_system import AuditLog, audit_manager

pytestmark = [pytest.mark.api, pytest.mark.security]


def _seed_event(action: str, username: str, ts: datetime) -> None:
    audit_manager.log_action(
        username=username,
        action=action,
        role="admin",
        details={"seed": True},
        success=True,
    )

    session = get_session()
    try:
        row = (
            session.query(AuditLog)
            .filter(AuditLog.action == action, AuditLog.username == username)
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert row is not None
        row.timestamp = ts
        session.commit()
    finally:
        session.close()


def test_security_incremental_export_requires_admin(client: TestClient, operator_headers: dict[str, str]) -> None:
    since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()

    unauthorized = client.get("/api/audit/security-events-export", params={"since": since})
    assert unauthorized.status_code == 401

    forbidden = client.get(
        "/api/audit/security-events-export",
        params={"since": since},
        headers=operator_headers,
    )
    assert forbidden.status_code == 403


def test_security_incremental_export_filters_orders_and_limits(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    base = datetime.now(timezone.utc) - timedelta(minutes=20)
    since = base + timedelta(minutes=5)

    _seed_event("SECURITY_LOGIN_FAILED", "export_u1", base + timedelta(minutes=1))
    _seed_event("SECURITY_WS_UNAUTHORIZED", "export_u2", base + timedelta(minutes=6))
    _seed_event("SECURITY_REFRESH_FAILED", "export_u3", base + timedelta(minutes=7))
    _seed_event("LOGIN", "export_non_security", base + timedelta(minutes=8))

    response = client.get(
        "/api/audit/security-events-export",
        params={"since": since.isoformat(), "limit": 2},
        headers=admin_headers,
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["count"] == 2
    assert payload["limit"] == 2
    assert payload["has_more"] is True

    events = payload["events"]
    assert len(events) == 2
    assert [item["action"] for item in events] == ["SECURITY_WS_UNAUTHORIZED", "SECURITY_REFRESH_FAILED"]
    assert events[0]["timestamp"] <= events[1]["timestamp"]
    assert payload["next_since"] == events[-1]["timestamp"]


def test_security_incremental_export_cursor_progression(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    base = datetime.now(timezone.utc) - timedelta(minutes=30)

    _seed_event("SECURITY_LOGIN_FAILED", "cursor_u1", base + timedelta(minutes=1))
    _seed_event("SECURITY_LOGIN_LOCKOUT", "cursor_u2", base + timedelta(minutes=2))
    _seed_event("SECURITY_WS_INVALID_SCOPE", "cursor_u3", base + timedelta(minutes=3))

    first = client.get(
        "/api/audit/security-events-export",
        params={"since": base.isoformat(), "limit": 2},
        headers=admin_headers,
    )
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["count"] == 2

    second = client.get(
        "/api/audit/security-events-export",
        params={"since": first_payload["next_since"], "limit": 2},
        headers=admin_headers,
    )
    assert second.status_code == 200
    second_payload = second.json()

    assert second_payload["count"] == 1
    assert second_payload["events"][0]["action"] == "SECURITY_WS_INVALID_SCOPE"
    assert second_payload["has_more"] is False
