"""Phase 1Q snapshot integrity verification endpoint tests."""

from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.api, pytest.mark.security]


def test_snapshot_verification_requires_admin(client: TestClient, operator_headers: dict[str, str]) -> None:
    payload = {"snapshot": {}, "integrity": {}}

    unauthorized = client.post("/api/audit/security-incident-snapshot-verify", json=payload)
    assert unauthorized.status_code == 401

    forbidden = client.post("/api/audit/security-incident-snapshot-verify", json=payload, headers=operator_headers)
    assert forbidden.status_code == 403


def test_snapshot_verification_accepts_valid_signed_payload(client: TestClient, admin_headers: dict[str, str]) -> None:
    signed = client.get("/api/audit/security-incident-snapshot-signed", headers=admin_headers)
    assert signed.status_code == 200
    signed_payload = signed.json()

    verify = client.post("/api/audit/security-incident-snapshot-verify", json=signed_payload, headers=admin_headers)
    assert verify.status_code == 200

    verification = (verify.json() or {}).get("verification") or {}
    assert verification.get("valid") is True
    assert verification.get("hash_valid") is True
    assert verification.get("signature_valid") is True


def test_snapshot_verification_rejects_tampered_payload(client: TestClient, admin_headers: dict[str, str]) -> None:
    signed = client.get("/api/audit/security-incident-snapshot-signed", headers=admin_headers)
    assert signed.status_code == 200
    payload = copy.deepcopy(signed.json())

    payload["snapshot"]["status"] = "incident" if payload["snapshot"].get("status") != "incident" else "healthy"

    verify = client.post("/api/audit/security-incident-snapshot-verify", json=payload, headers=admin_headers)
    assert verify.status_code == 200

    verification = (verify.json() or {}).get("verification") or {}
    assert verification.get("valid") is False
    assert verification.get("hash_valid") is False or verification.get("signature_valid") is False
