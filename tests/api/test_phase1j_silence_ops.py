"""Phase 1J silence operations tests (status, renew, clear)."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.services.audit_system import log_security_event

pytestmark = [pytest.mark.api, pytest.mark.security]


def _create_and_silence_security_alert(client: TestClient, admin_headers: dict[str, str]) -> str:
    log_security_event("refresh_failed", username="admin", role="admin", success=False, details={"reason": "test"})
    creation = client.get(
        "/api/audit/security-anomalies",
        params={
            "window_minutes": 60,
            "refresh_failed_threshold": 1,
            "auto_create_alert": "true",
        },
        headers=admin_headers,
    )
    assert creation.status_code == 200
    alert_id = (creation.json().get("security_alert") or {}).get("alert_id")
    assert alert_id

    ack = client.put(
        f"/api/alerts/{alert_id}/acknowledge-security",
        params={"silence_minutes": 30, "reason": "maintenance"},
        headers=admin_headers,
    )
    assert ack.status_code == 200
    fingerprint = ack.json().get("fingerprint")
    assert fingerprint
    return fingerprint


def test_security_silence_status_lists_active_entries(client: TestClient, admin_headers: dict[str, str]) -> None:
    fingerprint = _create_and_silence_security_alert(client, admin_headers)

    response = client.get("/api/audit/security-silences", headers=admin_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload.get("count", 0) >= 1
    silences = payload.get("silences", [])
    entry = next((item for item in silences if item.get("fingerprint") == fingerprint), None)
    assert entry is not None
    assert int(entry.get("remaining_seconds", 0)) > 0


def test_security_silence_can_be_renewed(client: TestClient, admin_headers: dict[str, str]) -> None:
    fingerprint = _create_and_silence_security_alert(client, admin_headers)

    before = client.get("/api/audit/security-silences", headers=admin_headers)
    assert before.status_code == 200
    before_entry = next(
        item for item in before.json().get("silences", []) if item.get("fingerprint") == fingerprint
    )
    before_until = datetime.fromisoformat(before_entry["silenced_until"])

    renew = client.post(
        "/api/audit/security-silences/renew",
        params={"fingerprint": fingerprint, "minutes": 120},
        headers=admin_headers,
    )
    assert renew.status_code == 200

    after_until = datetime.fromisoformat(renew.json()["silenced_until"])
    assert after_until > before_until


def test_security_silence_can_be_cleared(client: TestClient, admin_headers: dict[str, str]) -> None:
    fingerprint = _create_and_silence_security_alert(client, admin_headers)

    clear = client.delete(
        "/api/audit/security-silences",
        params={"fingerprint": fingerprint},
        headers=admin_headers,
    )
    assert clear.status_code == 200
    assert clear.json().get("cleared") is True

    status = client.get("/api/audit/security-silences", headers=admin_headers)
    assert status.status_code == 200
    silences = status.json().get("silences", [])
    assert all(item.get("fingerprint") != fingerprint for item in silences)
