"""Phase 6S contracts for secure container registry login in deploy workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_ci_deploy_uses_password_stdin_for_ghcr_login() -> None:
    text = _read(".github/workflows/ci.yml")

    assert "docker login ghcr.io -u \"${{ github.actor }}\" --password-stdin" in text
    assert "echo \"${{ secrets.GITHUB_TOKEN }}\" | docker login ghcr.io" in text
    assert "-p \"${{ secrets.GITHUB_TOKEN }}\"" not in text


def test_deployment_docs_recommend_password_stdin_for_registry_login() -> None:
    text = _read("docs/DEPLOYMENT.md")

    assert "docker login --password-stdin" in text
    assert "en lugar de `-p`" in text
