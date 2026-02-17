"""Phase 1B upload/input hardening tests."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.api, pytest.mark.security]


def test_media_upload_rejects_invalid_message_type(client: TestClient, operator_headers: dict[str, str]) -> None:
    files = {"file": ("photo.jpg", io.BytesIO(b"fake-jpeg"), "image/jpeg")}
    response = client.post(
        "/api/media/upload?messageType=../../../bad",
        files=files,
        headers=operator_headers,
    )
    assert response.status_code == 400


def test_media_upload_rejects_mime_extension_mismatch(client: TestClient, operator_headers: dict[str, str]) -> None:
    files = {"file": ("malicious.exe", io.BytesIO(b"fake-jpeg"), "image/jpeg")}
    response = client.post(
        "/api/media/upload?messageType=manual",
        files=files,
        headers=operator_headers,
    )
    assert response.status_code == 400


def test_media_upload_sanitizes_original_filename(client: TestClient, operator_headers: dict[str, str]) -> None:
    files = {"file": ("../../../../../evil.jpg", io.BytesIO(b"fake-jpeg"), "image/jpeg")}
    response = client.post(
        "/api/media/upload?messageType=manual",
        files=files,
        headers=operator_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True
    assert payload.get("originalName") == "evil.jpg"
    assert "/" not in payload.get("fileId", "") and "\\" not in payload.get("fileId", "")


def test_calendar_google_credentials_requires_json_extension(client: TestClient, admin_headers: dict[str, str]) -> None:
    files = {"credentials": ("creds.txt", io.BytesIO(b"{}"), "text/plain")}
    response = client.post(
        "/api/calendar/google/credentials",
        files=files,
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_business_config_import_rejects_invalid_json(client: TestClient, admin_headers: dict[str, str]) -> None:
    files = {"file": ("config.json", io.BytesIO(b"{invalid json"), "application/json")}
    response = client.post(
        "/api/business/config/import",
        files=files,
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_business_config_import_rejects_oversized_file(client: TestClient, admin_headers: dict[str, str]) -> None:
    large_content = b"{" + (b"a" * 2_100_000) + b"}"
    files = {"file": ("config.json", io.BytesIO(large_content), "application/json")}
    response = client.post(
        "/api/business/config/import",
        files=files,
        headers=admin_headers,
    )
    assert response.status_code == 413
