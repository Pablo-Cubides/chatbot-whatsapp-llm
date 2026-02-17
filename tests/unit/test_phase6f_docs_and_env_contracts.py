"""Phase 6F documentation and environment contract checks."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    file_path = ROOT / path
    assert file_path.exists(), f"Missing file: {path}"
    return file_path.read_text(encoding="utf-8")


def test_contributing_includes_precommit_install_steps() -> None:
    text = _read("CONTRIBUTING.md")
    assert "pre-commit install" in text
    assert "pre-commit run --all-files" in text


def test_readme_documents_pinned_python_patch_policy() -> None:
    text = _read("README.md")
    assert "python:3.11.8-slim" in text


def test_env_example_has_required_optional_debug_sections_and_redis_password() -> None:
    text = _read(".env.example")

    assert "# REQUIRED VARIABLES" in text
    assert "# OPTIONAL VARIABLES" in text
    assert "# DEBUG / LOCAL DEV" in text
    assert "REDIS_PASSWORD=" in text
