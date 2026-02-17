"""Basic Alembic migration integrity checks."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = ROOT / "alembic.ini"


def _has_alembic_cli() -> bool:
    try:
        result = subprocess.run(["alembic", "--help"], cwd=ROOT, capture_output=True, text=True, check=False)
        return result.returncode == 0
    except OSError:
        return False


def _alembic_env() -> dict[str, str]:
    env = os.environ.copy()
    # Isolate migration test DB to avoid touching default runtime file
    env["DATABASE_URL"] = f"sqlite:///{(ROOT / 'alembic_test.db').as_posix()}"
    return env


def test_alembic_no_duplicate_revision_ids() -> None:
    if not ALEMBIC_INI.exists():
        pytest.skip("alembic.ini no encontrado")

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    script = ScriptDirectory.from_config(cfg)

    revisions = list(script.walk_revisions())
    revision_ids = [rev.revision for rev in revisions]
    assert len(revision_ids) == len(set(revision_ids))


def test_alembic_heads_consistency() -> None:
    if not ALEMBIC_INI.exists():
        pytest.skip("alembic.ini no encontrado")

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    script = ScriptDirectory.from_config(cfg)

    heads = script.get_heads()
    assert heads, "No Alembic heads found"


def test_alembic_upgrade_and_downgrade_smoke() -> None:
    if not ALEMBIC_INI.exists():
        pytest.skip("alembic.ini no encontrado")

    if not _has_alembic_cli():
        pytest.skip("Alembic CLI no disponible en entorno")

    env = _alembic_env()

    up = subprocess.run(["alembic", "upgrade", "head"], cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    if up.returncode != 0:
        combined = (up.stderr or "") + "\n" + (up.stdout or "")
        if "No support for ALTER of constraints in SQLite dialect" in combined:
            pytest.skip("SQLite no soporta ALTER constraint para esta migración; validar en PostgreSQL")
        assert up.returncode == 0, up.stderr or up.stdout

    down = subprocess.run(["alembic", "downgrade", "-1"], cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    assert down.returncode == 0, down.stderr or down.stdout

    # Return to head so DB state remains valid for local reruns
    up_again = subprocess.run(["alembic", "upgrade", "head"], cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    assert up_again.returncode == 0, up_again.stderr or up_again.stdout
