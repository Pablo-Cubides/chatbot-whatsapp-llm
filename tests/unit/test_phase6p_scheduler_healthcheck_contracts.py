"""Phase 6P contracts for scheduler liveness healthcheck hardening."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_scheduler_healthcheck_validates_scheduler_worker_process() -> None:
    text = _read("docker-compose.yml")

    scheduler_start = text.find("  scheduler:")
    assert scheduler_start != -1

    redis_start = text.find("  # Redis para caché avanzado", scheduler_start)
    assert redis_start != -1

    scheduler_block = text[scheduler_start:redis_start]

    assert "healthcheck:" in scheduler_block
    assert "glob.glob('/proc/[0-9]*/cmdline')" in scheduler_block
    assert "src.workers.scheduler_worker" in scheduler_block
    assert "scheduler_worker.py" in scheduler_block
    assert "sys.exit(0 if ok else 1)" in scheduler_block
