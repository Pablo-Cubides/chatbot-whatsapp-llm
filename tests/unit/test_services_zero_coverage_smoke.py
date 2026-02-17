from datetime import datetime

import pytest

from src.services.calendar_service import CalendarConfig, CalendarProvider, TimeSlot
from src.services.chat_system import ChatConnectionManager
from src.services.google_calendar_provider import GoogleCalendarProvider
from src.services.image_analyzer import ImageAnalyzer
from src.services.outlook_calendar_provider import OutlookCalendarProvider
from src.services.realtime_metrics import RealtimeMetricsManager
from src.services.whatsapp_system import WhatsAppManager
from src.workers.scheduler_worker import SchedulerWorker


def test_calendar_service_timeslot_and_config() -> None:
    slot = TimeSlot(start=datetime(2026, 2, 13, 10, 0), end=datetime(2026, 2, 13, 10, 30))
    data = slot.to_dict()

    assert data["duration_minutes"] == 30
    assert "10:00" in slot.format_for_user()

    cfg = CalendarConfig(
        provider=CalendarProvider.GOOGLE_CALENDAR,
        working_hours={"monday": {"start": "09:00", "end": "18:00", "closed": False}},
    )
    assert cfg.get_working_hours_for_day("monday") is not None


def test_chat_system_manager_stats_initial() -> None:
    manager = ChatConnectionManager()
    stats = manager.get_session_stats()
    assert stats["active_connections"] == 0
    assert stats["total_sessions"] == 0


@pytest.mark.asyncio
async def test_google_provider_basic_properties() -> None:
    provider = GoogleCalendarProvider(CalendarConfig(provider=CalendarProvider.GOOGLE_CALENDAR))
    assert provider.provider_name == "google_calendar"
    # No credentials file by default in test env => None, but function should be safe
    _ = provider.get_oauth_url()


@pytest.mark.asyncio
async def test_outlook_provider_basic_properties() -> None:
    provider = OutlookCalendarProvider(CalendarConfig(provider=CalendarProvider.OUTLOOK))
    assert provider.provider_name == "outlook"
    _ = provider.get_oauth_url()


@pytest.mark.asyncio
async def test_image_analyzer_disabled_mode() -> None:
    analyzer = ImageAnalyzer()
    analyzer.enabled = False

    result = await analyzer.analyze_image(b"img")
    assert result["success"] is False
    assert "deshabilitado" in result["error"].lower()


def test_realtime_metrics_distribution_and_snapshot() -> None:
    mgr = RealtimeMetricsManager()
    mgr.record_llm_usage("gemini", tokens=100, response_time=0.9)
    mgr.record_llm_usage("gemini", tokens=100, response_time=3.4)
    mgr.record_error("runtime", "boom")

    snapshot = mgr.get_current_metrics()
    assert "overview" in snapshot
    dist = mgr._get_response_time_distribution(
        [
            {"time": 0.5, "timestamp": datetime.now()},
            {"time": 2.0, "timestamp": datetime.now()},
            {"time": 7.0, "timestamp": datetime.now()},
        ]
    )
    assert dist["0-1s"] == 1
    assert dist["1-3s"] == 1
    assert dist["5-10s"] == 1


def test_whatsapp_system_status_smoke() -> None:
    manager = WhatsAppManager()
    status = manager.get_status()
    assert status["is_running"] is False
    assert status["active_chats"] == 0


def test_scheduler_worker_processes_due_messages(monkeypatch) -> None:
    worker = SchedulerWorker()

    captured = {"calls": 0}

    def _fake_get_pending_messages(limit=10, include_scheduled=True):
        captured["calls"] += 1
        return [{"message_id": "msg_test", "status": "pending"}]

    monkeypatch.setattr("src.workers.scheduler_worker.queue_manager.get_pending_messages", _fake_get_pending_messages)

    worker.process_scheduled_messages()

    assert captured["calls"] == 1
