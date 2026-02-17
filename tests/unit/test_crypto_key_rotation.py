import os
import time

from crypto import is_key_rotation_due


def test_key_rotation_due_true_for_old_key(monkeypatch, tmp_path):
    key_file = tmp_path / "fernet.key"
    key_file.write_bytes(b"A" * 44)

    old_ts = time.time() - (120 * 86400)
    os.utime(key_file, (old_ts, old_ts))

    monkeypatch.setattr("crypto.KEY_PATH", str(key_file))
    due, age_days = is_key_rotation_due(rotation_days=90)

    assert due is True
    assert age_days >= 90


def test_key_rotation_due_false_for_recent_key(monkeypatch, tmp_path):
    key_file = tmp_path / "fernet.key"
    key_file.write_bytes(b"B" * 44)

    monkeypatch.setattr("crypto.KEY_PATH", str(key_file))
    due, age_days = is_key_rotation_due(rotation_days=90)

    assert due is False
    assert age_days >= 0
