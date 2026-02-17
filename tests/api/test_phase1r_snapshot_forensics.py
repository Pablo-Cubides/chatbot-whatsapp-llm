"""Phase 1R forensic audit tests for snapshot verification operations."""

from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.api, pytest.mark.security]


def test_snapshot_verification_logs_success_audit_event(client: TestClient, admin_headers: dict[str, str]) -> None:
    signed = client.get("/api/audit/security-incident-snapshot-signed", headers=admin_headers)
    assert signed.status_code == 200

    verify = client.post("/api/audit/security-incident-snapshot-verify", json=signed.json(), headers=admin_headers)
    assert verify.status_code == 200
    assert (verify.json().get("verification") or {}).get("valid") is True

    logs_response = client.get(
        "/api/audit/logs",
        params={"action": "SECURITY_SNAPSHOT_VERIFICATION_PERFORMED", "limit": 5},
        headers=admin_headers,
    )
    assert logs_response.status_code == 200

    logs = logs_response.json().get("logs", [])
    assert logs
    details = logs[0].get("details") or {}
    assert details.get("valid") is True
    assert details.get("hash_valid") is True


def test_snapshot_verification_logs_failed_audit_event(client: TestClient, admin_headers: dict[str, str]) -> None:
    signed = client.get("/api/audit/security-incident-snapshot-signed", headers=admin_headers)
    assert signed.status_code == 200
    tampered = copy.deepcopy(signed.json())
    tampered["snapshot"]["status"] = "incident" if tampered["snapshot"].get("status") != "incident" else "healthy"

    verify = client.post("/api/audit/security-incident-snapshot-verify", json=tampered, headers=admin_headers)
    assert verify.status_code == 200
    assert (verify.json().get("verification") or {}).get("valid") is False

    logs_response = client.get(
        "/api/audit/logs",
        params={"action": "SECURITY_SNAPSHOT_VERIFICATION_PERFORMED", "limit": 10},
        headers=admin_headers,
    )
    assert logs_response.status_code == 200

    logs = logs_response.json().get("logs", [])
    assert logs
    assert any(((entry.get("details") or {}).get("valid") is False) for entry in logs)
