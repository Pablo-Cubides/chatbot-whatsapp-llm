"""Phase 6E packaging/path hygiene contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_pyproject_exists_for_editable_install() -> None:
    text = _read("pyproject.toml")
    assert "[build-system]" in text
    assert "setuptools.build_meta" in text
    assert "name = \"chatbot-whatsapp-llm\"" in text


def test_conftest_has_no_sys_path_insert_hacks() -> None:
    text = _read("conftest.py")
    assert "sys.path.insert" not in text


def test_scheduler_worker_has_no_sys_path_insert_hacks() -> None:
    text = _read("src/workers/scheduler_worker.py")
    assert "sys.path.insert" not in text


def test_scheduler_dockerfile_runs_module_entrypoint() -> None:
    text = _read("Dockerfile.scheduler")
    assert 'CMD ["python", "-m", "src.workers.scheduler_worker"]' in text
