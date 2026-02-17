"""Phase 6B operational controls: request-id tracing, env validation, and process audit logging."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import crypto
from admin_panel import validate_runtime_environment
from src.services import process_control

pytestmark = pytest.mark.unit


def test_request_id_header_is_propagated(client: TestClient) -> None:
    response = client.get("/", headers={"X-Request-ID": "req-custom-123"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "req-custom-123"


def test_request_id_header_is_generated_when_missing(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200

    request_id = response.headers.get("X-Request-ID", "")
    assert request_id
    assert len(request_id) >= 16


def test_runtime_env_validation_requires_whatsapp_app_secret_in_cloud_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHATSAPP_MODE", "cloud")
    monkeypatch.delenv("WHATSAPP_APP_SECRET", raising=False)

    with pytest.raises(RuntimeError):
        validate_runtime_environment()


def test_process_kill_logs_audit_when_psutil_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_calls: list[dict] = []

    def _fake_log_action(*_args, **kwargs):
        captured_calls.append(kwargs)
        return True

    monkeypatch.setattr(process_control, "psutil", None)
    monkeypatch.setattr(process_control.audit_manager, "log_action", _fake_log_action)

    killed = process_control.kill_by_port(1234, username="admin", role="admin", reason="test-reason")

    assert killed == []
    assert captured_calls
    payload = captured_calls[-1]
    assert payload.get("action") == "PROCESS_KILL_BY_PORT"
    assert payload.get("username") == "admin"
    assert (payload.get("details") or {}).get("reason") == "test-reason"


def test_ensure_key_uses_atomic_create_exclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key_path = tmp_path / "fernet.key"
    observed_flags: list[int] = []

    original_open = crypto.os.open

    def _tracking_open(path: str, flags: int, mode: int = 0o777):
        observed_flags.append(flags)
        return original_open(path, flags, mode)

    monkeypatch.setattr(crypto, "KEY_PATH", str(key_path))
    monkeypatch.setattr(crypto.os, "open", _tracking_open)

    key = crypto.ensure_key()

    assert key
    assert key_path.exists()
    assert observed_flags
    assert any((flags & os.O_EXCL) != 0 for flags in observed_flags)
