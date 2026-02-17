"""Phase 6M contracts for proxy and backup compose overlays."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_proxy_overlay_depends_on_healthy_app_and_limits_resources() -> None:
    text = _read("docker-compose.proxy.yml")

    assert "reverse-proxy:" in text
    assert "condition: service_healthy" in text
    assert "restart: unless-stopped" in text
    assert "mem_limit: 256m" in text
    assert 'cpus: "0.50"' in text


def test_nginx_reverse_proxy_keeps_forward_headers_and_security_headers() -> None:
    text = _read("config/nginx/default.conf")

    assert "proxy_set_header X-Real-IP $remote_addr;" in text
    assert "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;" in text
    assert "proxy_set_header X-Forwarded-Proto $scheme;" in text
    assert "add_header Strict-Transport-Security \"max-age=31536000; includeSubDomains\" always;" in text
    assert "add_header X-Content-Type-Options \"nosniff\" always;" in text
    assert "add_header X-Frame-Options \"DENY\" always;" in text
    assert "add_header Referrer-Policy \"strict-origin-when-cross-origin\" always;" in text


def test_backup_overlay_requires_db_password_and_retention_controls() -> None:
    text = _read("docker-compose.backup.yml")

    assert "postgres-backup:" in text
    assert "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD?POSTGRES_PASSWORD is required}" in text
    assert "SCHEDULE: ${BACKUP_SCHEDULE:-@daily}" in text
    assert "BACKUP_KEEP_DAYS: ${BACKUP_KEEP_DAYS:-7}" in text
    assert "BACKUP_KEEP_WEEKS: ${BACKUP_KEEP_WEEKS:-4}" in text
    assert "BACKUP_KEEP_MONTHS: ${BACKUP_KEEP_MONTHS:-6}" in text
    assert "condition: service_healthy" in text
    assert "restart: unless-stopped" in text
