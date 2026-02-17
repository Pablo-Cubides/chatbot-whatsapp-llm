"""Phase 5D infra-quality checks for docker compose integrity."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit



def test_docker_compose_worker_web_environment_block_integrity() -> None:
    compose_path = Path(__file__).resolve().parents[2] / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml not found"

    text = compose_path.read_text(encoding="utf-8")
    assert "worker-web:" in text

    start_idx = text.find("  worker-web:")
    assert start_idx != -1

    end_idx = text.find("  # Worker para Scheduler", start_idx)
    if end_idx == -1:
        end_idx = text.find("  scheduler:", start_idx)
    assert end_idx != -1

    worker_block = text[start_idx:end_idx]

    assert worker_block.count("\n    environment:") == 1
    assert "DATABASE_URL:" in worker_block
    assert "WHATSAPP_MODE:" in worker_block
    assert "DISPLAY:" in worker_block



def test_docker_compose_has_no_stray_single_letter_line_from_snapshot() -> None:
    compose_path = Path(__file__).resolve().parents[2] / "docker-compose.yml"
    text = compose_path.read_text(encoding="utf-8")

    bad_lines = [line for line in text.splitlines() if line.strip() == "e"]
    assert not bad_lines
