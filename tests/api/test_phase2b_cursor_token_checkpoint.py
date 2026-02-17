"""Phase 2B cursor token + checkpoint workflows for SECURITY export."""

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


def test_security_export_v2_rejects_tampered_cursor_token(client: TestClient, admin_headers: dict[str, str]) -> None:
    base = datetime.now(timezone.utc) - timedelta(minutes=15)
    _seed_event("SECURITY_LOGIN_FAILED", "phase2b_tamper", base + timedelta(minutes=1))

    first = client.get(
        "/api/audit/security-events-export-v2",
        params={"since": base.isoformat(), "after_id": 0, "limit": 1},
        headers=admin_headers,
    )
    assert first.status_code == 200
    token = first.json().get("cursor_token")
    assert isinstance(token, str) and token

    tampered = f"{token[:-1]}A" if len(token) > 1 else "A"
    invalid = client.get(
        "/api/audit/security-events-export-v2",
        params={"cursor_token": tampered, "limit": 1},
        headers=admin_headers,
    )
    assert invalid.status_code == 400


def test_security_export_v2_cursor_token_resume(client: TestClient, admin_headers: dict[str, str]) -> None:
    base = (datetime.now(timezone.utc) - timedelta(minutes=40)).replace(microsecond=0)

    _seed_event("SECURITY_LOGIN_FAILED", "phase2b_resume_1", base + timedelta(minutes=1))
    _seed_event("SECURITY_LOGIN_LOCKOUT", "phase2b_resume_2", base + timedelta(minutes=2))
    _seed_event("SECURITY_WS_INVALID_SCOPE", "phase2b_resume_3", base + timedelta(minutes=3))

    first = client.get(
        "/api/audit/security-events-export-v2",
        params={"since": base.isoformat(), "after_id": 0, "limit": 2},
        headers=admin_headers,
    )
    assert first.status_code == 200
    p1 = first.json()
    assert p1["count"] == 2
    token = p1.get("cursor_token")
    assert isinstance(token, str) and token

    second = client.get(
        "/api/audit/security-events-export-v2",
        params={"cursor_token": token, "limit": 2},
        headers=admin_headers,
    )
    assert second.status_code == 200
    p2 = second.json()

    assert p2["count"] == 1
    assert p2["events"][0]["action"] == "SECURITY_WS_INVALID_SCOPE"
    assert p2["has_more"] is False


def test_security_export_checkpoints_crud_and_authz(
    client: TestClient,
    admin_headers: dict[str, str],
    operator_headers: dict[str, str],
) -> None:
    since = (datetime.now(timezone.utc) - timedelta(minutes=3)).replace(microsecond=0)

    unauthorized = client.put(
        "/api/audit/security-export-checkpoints/siem-main",
        params={"since": since.isoformat(), "after_id": 9},
    )
    assert unauthorized.status_code == 401

    forbidden = client.put(
        "/api/audit/security-export-checkpoints/siem-main",
        params={"since": since.isoformat(), "after_id": 9},
        headers=operator_headers,
    )
    assert forbidden.status_code == 403

    upsert = client.put(
        "/api/audit/security-export-checkpoints/siem-main",
        params={"since": since.isoformat(), "after_id": 9},
        headers=admin_headers,
    )
    assert upsert.status_code == 200
    checkpoint = (upsert.json().get("checkpoint") or {})
    assert checkpoint.get("consumer") == "siem-main"
    assert int(checkpoint.get("after_id", -1)) == 9

    fetched = client.get("/api/audit/security-export-checkpoints/siem-main", headers=admin_headers)
    assert fetched.status_code == 200
    stored = (fetched.json().get("checkpoint") or {})
    assert stored.get("consumer") == "siem-main"
    assert int(stored.get("after_id", -1)) == 9

    listed = client.get("/api/audit/security-export-checkpoints", headers=admin_headers)
    assert listed.status_code == 200
    items = listed.json().get("items") or []
    assert any(item.get("consumer") == "siem-main" for item in items)
