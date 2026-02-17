"""Phase 1P signed snapshot integrity export tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.api, pytest.mark.security]


def test_signed_snapshot_requires_admin(client: TestClient, operator_headers: dict[str, str]) -> None:
    unauthorized = client.get("/api/audit/security-incident-snapshot-signed")
    assert unauthorized.status_code == 401

    forbidden = client.get("/api/audit/security-incident-snapshot-signed", headers=operator_headers)
    assert forbidden.status_code == 403


def test_signed_snapshot_returns_valid_hash_and_signature(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get(
        "/api/audit/security-incident-snapshot-signed",
        params={"window_minutes": 60, "recent_events_limit": 10},
        headers=admin_headers,
    )
    assert response.status_code == 200

    payload = response.json()
    snapshot = payload.get("snapshot") or {}
    integrity = payload.get("integrity") or {}

    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    expected_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    assert integrity.get("canonical_json") == canonical
    assert integrity.get("content_sha256") == expected_sha
    assert integrity.get("signed") is True
    assert integrity.get("signature_algorithm") == "HMAC-SHA256"

    signing_key = (os.environ.get("SECURITY_SNAPSHOT_SIGNING_KEY") or os.environ.get("JWT_SECRET") or "").encode("utf-8")
    expected_sig = hmac.new(signing_key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    assert integrity.get("signature") == expected_sig
