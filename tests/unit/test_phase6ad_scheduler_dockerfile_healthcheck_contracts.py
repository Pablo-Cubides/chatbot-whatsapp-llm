"""Phase 6AD contracts for Dockerfile.scheduler HEALTHCHECK hardening."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_scheduler_dockerfile_defines_process_liveness_healthcheck() -> None:
    text = _read("Dockerfile.scheduler")

    assert "HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3" in text
    assert "CMD python -c" in text
    assert "/proc/[0-9]*/cmdline" in text
    assert "src.workers.scheduler_worker" in text
    assert "scheduler_worker.py" in text
