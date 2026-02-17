"""Phase 3C schema creation control tests."""

from __future__ import annotations

from src.models import admin_db


def test_initialize_schema_skips_when_create_all_disabled(monkeypatch) -> None:
    called = {"value": False}

    def _fake_create_all(_engine):
        called["value"] = True

    monkeypatch.setattr(admin_db, "ALLOW_CREATE_ALL", False)
    monkeypatch.setattr(admin_db.Base.metadata, "create_all", _fake_create_all)

    admin_db.initialize_schema()
    assert called["value"] is False


def test_initialize_schema_runs_when_create_all_enabled(monkeypatch) -> None:
    called = {"value": False}

    def _fake_create_all(_engine):
        called["value"] = True

    monkeypatch.setattr(admin_db, "ALLOW_CREATE_ALL", True)
    monkeypatch.setattr(admin_db.Base.metadata, "create_all", _fake_create_all)

    admin_db.initialize_schema()
    assert called["value"] is True
