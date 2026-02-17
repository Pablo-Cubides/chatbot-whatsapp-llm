"""Phase 1T retention/compliance tests for SECURITY_* forensic events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.models.admin_db import get_session
from src.services.audit_system import AuditLog, audit_manager

pytestmark = [pytest.mark.api, pytest.mark.security]


def _create_old_security_event(action: str, username: str) -> None:
    audit_manager.log_action(username=username, action=action, role="admin", details={"seed": True}, success=True)
    session = get_session()
    try:
        row = session.query(AuditLog).filter(AuditLog.action == action, AuditLog.username == username).order_by(AuditLog.id.desc()).first()
        assert row is not None
        row.timestamp = datetime.now(timezone.utc) - timedelta(days=400)
        session.commit()
    finally:
        session.close()


def test_security_retention_policy_requires_admin(client: TestClient, operator_headers: dict[str, str]) -> None:
    unauthorized = client.get("/api/audit/security-retention-policy")
    assert unauthorized.status_code == 401

    forbidden = client.get("/api/audit/security-retention-policy", headers=operator_headers)
    assert forbidden.status_code == 403


def test_security_retention_dry_run_reports_candidates_without_deleting(client: TestClient, admin_headers: dict[str, str]) -> None:
    _create_old_security_event("SECURITY_LOGIN_FAILED", "old_retention_user")

    preview = client.get(
        "/api/audit/security-retention-policy",
        params={"retention_days": 365},
        headers=admin_headers,
    )
    assert preview.status_code == 200
    candidate_count = (preview.json().get("preview") or {}).get("count", 0)
    assert candidate_count >= 1

    dry_run = client.post(
        "/api/audit/security-retention-purge",
        params={"retention_days": 365, "dry_run": "true"},
        headers=admin_headers,
    )
    assert dry_run.status_code == 200
    result = dry_run.json().get("result") or {}
    assert result.get("dry_run") is True
    assert int(result.get("deleted_count", 0)) == 0


def test_security_retention_purge_deletes_old_non_protected_events(client: TestClient, admin_headers: dict[str, str]) -> None:
    _create_old_security_event("SECURITY_LOGIN_FAILED", "purge_target_user")
    _create_old_security_event("SECURITY_SNAPSHOT_VERIFICATION_PERFORMED", "protected_user")

    execute = client.post(
        "/api/audit/security-retention-purge",
        params={"retention_days": 365, "dry_run": "false", "include_protected_actions": "false"},
        headers=admin_headers,
    )
    assert execute.status_code == 200
    result = execute.json().get("result") or {}
    assert result.get("dry_run") is False
    assert int(result.get("deleted_count", 0)) >= 1

    purged_logs = client.get(
        "/api/audit/logs",
        params={"action": "SECURITY_LOGIN_FAILED", "username": "purge_target_user"},
        headers=admin_headers,
    )
    assert purged_logs.status_code == 200
    assert purged_logs.json().get("count", 0) == 0

    protected_logs = client.get(
        "/api/audit/logs",
        params={"action": "SECURITY_SNAPSHOT_VERIFICATION_PERFORMED", "username": "protected_user"},
        headers=admin_headers,
    )
    assert protected_logs.status_code == 200
    assert protected_logs.json().get("count", 0) >= 1
