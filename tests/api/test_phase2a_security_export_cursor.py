"""Phase 2A cursor-safe incremental SECURITY_* export tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
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


def test_security_incremental_export_v2_requires_admin(client: TestClient, operator_headers: dict[str, str]) -> None:
    since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()

    unauthorized = client.get("/api/audit/security-events-export-v2", params={"since": since})
    assert unauthorized.status_code == 401

    forbidden = client.get(
        "/api/audit/security-events-export-v2",
        params={"since": since},
        headers=operator_headers,
    )
    assert forbidden.status_code == 403


def test_security_incremental_export_v2_cursor_handles_same_timestamp(client: TestClient, admin_headers: dict[str, str]) -> None:
    base = (datetime.now(timezone.utc) - timedelta(minutes=25)).replace(microsecond=0)

    _seed_event("SECURITY_LOGIN_FAILED", "p2_cursor_1", base + timedelta(minutes=1))
    _seed_event("SECURITY_LOGIN_LOCKOUT", "p2_cursor_2", base + timedelta(minutes=1))
    _seed_event("SECURITY_WS_UNAUTHORIZED", "p2_cursor_3", base + timedelta(minutes=2))

    first = client.get(
        "/api/audit/security-events-export-v2",
        params={"since": base.isoformat(), "after_id": 0, "limit": 1},
        headers=admin_headers,
    )
    assert first.status_code == 200
    p1 = first.json()
    assert p1["count"] == 1

    second = client.get(
        "/api/audit/security-events-export-v2",
        params={"since": p1["cursor"]["since"], "after_id": p1["cursor"]["after_id"], "limit": 1},
        headers=admin_headers,
    )
    assert second.status_code == 200
    p2 = second.json()
    assert p2["count"] == 1

    third = client.get(
        "/api/audit/security-events-export-v2",
        params={"since": p2["cursor"]["since"], "after_id": p2["cursor"]["after_id"], "limit": 1},
        headers=admin_headers,
    )
    assert third.status_code == 200
    p3 = third.json()
    assert p3["count"] == 1

    ids = [p1["events"][0]["id"], p2["events"][0]["id"], p3["events"][0]["id"]]
    assert len(set(ids)) == 3
    assert ids[0] < ids[1] < ids[2]

    actions = [p1["events"][0]["action"], p2["events"][0]["action"], p3["events"][0]["action"]]
    assert actions == ["SECURITY_LOGIN_FAILED", "SECURITY_LOGIN_LOCKOUT", "SECURITY_WS_UNAUTHORIZED"]


def test_security_incremental_export_v2_batch_integrity(client: TestClient, admin_headers: dict[str, str]) -> None:
    base = datetime.now(timezone.utc) - timedelta(minutes=12)
    _seed_event("SECURITY_REFRESH_FAILED", "p2_integrity_1", base + timedelta(minutes=1))

    response = client.get(
        "/api/audit/security-events-export-v2",
        params={"since": base.isoformat(), "after_id": 0, "limit": 5},
        headers=admin_headers,
    )
    assert response.status_code == 200
    payload = response.json()

    batch_payload = {
        "since": payload["since"],
        "after_id": payload["after_id"],
        "limit": payload["limit"],
        "count": payload["count"],
        "cursor": payload["cursor"],
        "events": payload["events"],
    }
    canonical = json.dumps(batch_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    integrity = payload["integrity"]
    assert integrity["content_sha256"] == expected_hash

    signing_key = os.environ.get("SECURITY_SNAPSHOT_SIGNING_KEY") or os.environ.get("JWT_SECRET") or ""
    assert integrity["signed"] is bool(signing_key)

    if signing_key:
        expected_sig = hmac.new(signing_key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        assert integrity["signature_algorithm"] == "HMAC-SHA256"
        assert integrity["signature"] == expected_sig
