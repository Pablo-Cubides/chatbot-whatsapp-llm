"""Phase 2C consumer-oriented SECURITY export resume tests."""

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


def test_consumer_export_requires_admin(client: TestClient, operator_headers: dict[str, str]) -> None:
    unauthorized = client.post("/api/audit/security-events-export-v2/consumer/siem-core")
    assert unauthorized.status_code == 401

    forbidden = client.post(
        "/api/audit/security-events-export-v2/consumer/siem-core",
        headers=operator_headers,
    )
    assert forbidden.status_code == 403


def test_consumer_export_requires_bootstrap_without_checkpoint(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/audit/security-events-export-v2/consumer/new-consumer",
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_consumer_export_bootstrap_then_resume(client: TestClient, admin_headers: dict[str, str]) -> None:
    base = datetime.now(timezone.utc) - timedelta(minutes=35)

    _seed_event("SECURITY_LOGIN_FAILED", "phase2c_1", base + timedelta(minutes=1))
    _seed_event("SECURITY_LOGIN_LOCKOUT", "phase2c_2", base + timedelta(minutes=2))
    _seed_event("SECURITY_REFRESH_FAILED", "phase2c_3", base + timedelta(minutes=3))

    first = client.post(
        "/api/audit/security-events-export-v2/consumer/siem-core",
        params={"bootstrap_since": base.isoformat(), "limit": 2},
        headers=admin_headers,
    )
    assert first.status_code == 200
    p1 = first.json()
    assert p1["count"] == 2
    assert p1["checkpoint"]["consumer"] == "siem-core"

    second = client.post(
        "/api/audit/security-events-export-v2/consumer/siem-core",
        params={"limit": 2},
        headers=admin_headers,
    )
    assert second.status_code == 200
    p2 = second.json()

    assert p2["count"] == 1
    assert p2["events"][0]["action"] == "SECURITY_REFRESH_FAILED"
    assert p2["checkpoint"]["consumer"] == "siem-core"
