"""Phase 6A compose runtime/security guardrails."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def _compose_text() -> str:
    compose_path = Path(__file__).resolve().parents[2] / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml not found"
    return compose_path.read_text(encoding="utf-8")


def test_each_service_uses_single_environment_block() -> None:
    text = _compose_text()

    service_blocks = {
        "postgres": ("  postgres:", "  # API y Admin Panel"),
        "app": ("  app:", "  # Worker para WhatsApp Web (Playwright)"),
        "worker-web": ("  worker-web:", "  # Worker para Scheduler"),
        "scheduler": ("  scheduler:", "  # Redis para caché avanzado"),
        "redis": ("  redis:", "\nvolumes:\n"),
    }

    for service_name, (start_marker, end_marker) in service_blocks.items():
        start_idx = text.find(start_marker)
        assert start_idx != -1, f"{service_name} service block not found"

        end_idx = text.find(end_marker, start_idx)
        assert end_idx != -1, f"End marker for {service_name} block not found"

        block = text[start_idx:end_idx]
        assert block.count("\n    environment:") <= 1, f"{service_name} defines duplicated environment blocks"


def test_redis_healthcheck_authenticates_when_password_required() -> None:
    text = _compose_text()

    redis_start = text.find("  redis:")
    assert redis_start != -1

    redis_end = text.find("\nvolumes:\n", redis_start)
    assert redis_end != -1

    redis_block = text[redis_start:redis_end]

    assert "--requirepass ${REDIS_PASSWORD?REDIS_PASSWORD is required}" in redis_block
    assert "healthcheck:" in redis_block
    assert "redis-cli -a" in redis_block
    assert "${REDIS_PASSWORD?REDIS_PASSWORD is required}" in redis_block
    assert "ping" in redis_block


def test_compose_has_no_orphan_single_letter_line_e() -> None:
    text = _compose_text()
    assert not any(line.strip() == "e" for line in text.splitlines())
