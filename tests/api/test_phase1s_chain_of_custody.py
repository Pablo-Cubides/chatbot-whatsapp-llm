"""Phase 1S chain-of-custody reporting tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.api, pytest.mark.security]


def _emit_verification_event(client: TestClient, admin_headers: dict[str, str]) -> None:
    signed = client.get("/api/audit/security-incident-snapshot-signed", headers=admin_headers)
    assert signed.status_code == 200
    verify = client.post("/api/audit/security-incident-snapshot-verify", json=signed.json(), headers=admin_headers)
    assert verify.status_code == 200


def test_chain_of_custody_requires_admin(client: TestClient, operator_headers: dict[str, str]) -> None:
    unauthorized = client.get("/api/audit/security-chain-of-custody")
    assert unauthorized.status_code == 401

    forbidden = client.get("/api/audit/security-chain-of-custody", headers=operator_headers)
    assert forbidden.status_code == 403


def test_chain_of_custody_returns_verification_entries(client: TestClient, admin_headers: dict[str, str]) -> None:
    _emit_verification_event(client, admin_headers)

    response = client.get(
        "/api/audit/security-chain-of-custody",
        params={"hours_back": 24, "limit": 20},
        headers=admin_headers,
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload.get("count", 0) >= 1
    entries = payload.get("entries", [])
    assert entries

    first = entries[0]
    assert first.get("action") == "SECURITY_SNAPSHOT_VERIFICATION_PERFORMED"
    assert "verification_valid" in first
    assert "computed_content_sha256" in first


def test_chain_of_custody_respects_limit(client: TestClient, admin_headers: dict[str, str]) -> None:
    for _ in range(3):
        _emit_verification_event(client, admin_headers)

    response = client.get(
        "/api/audit/security-chain-of-custody",
        params={"hours_back": 24, "limit": 2},
        headers=admin_headers,
    )
    assert response.status_code == 200

    entries = response.json().get("entries", [])
    assert len(entries) <= 2
