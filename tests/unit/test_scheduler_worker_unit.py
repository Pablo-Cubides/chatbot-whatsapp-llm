import pytest

from src.workers.scheduler_worker import SchedulerWorker

pytestmark = pytest.mark.unit


def test_process_scheduled_messages_uses_db_queue_snapshot(monkeypatch) -> None:
    worker = SchedulerWorker()

    calls = {"count": 0}

    def _fake_get_pending_messages(limit=10, include_scheduled=True):
        calls["count"] += 1
        return [{"message_id": "m1"}]

    monkeypatch.setattr("src.workers.scheduler_worker.queue_manager.get_pending_messages", _fake_get_pending_messages)
    worker.process_scheduled_messages()
    assert calls["count"] == 1


def test_check_fernet_rotation_does_not_raise(monkeypatch) -> None:
    worker = SchedulerWorker()
    monkeypatch.setattr("src.workers.scheduler_worker.is_key_rotation_due", lambda rotation_days: (False, 3.2))
    worker.check_fernet_rotation()
