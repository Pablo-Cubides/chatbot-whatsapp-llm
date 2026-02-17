"""Unit tests for analytics system manager."""

import pytest

from src.services.analytics_system import AnalyticsManager

pytestmark = pytest.mark.unit


def test_analytics_dashboard_and_realtime_metrics(tmp_path) -> None:
    db_file = tmp_path / "analytics_test.db"
    manager = AnalyticsManager(db_path=str(db_file))

    manager.record_conversation_start("session-1", "user-1")
    manager.record_api_usage("openai", "/v1/chat/completions", 50, 120, success=True)
    manager.record_api_usage("openai", "/v1/chat/completions", 30, 100, success=False, error_message="boom")
    manager.record_conversation_end("session-1", message_count=2, satisfaction_score=4.5, converted=True)

    dashboard = manager.get_dashboard_metrics(hours=24)
    assert dashboard["conversations"]["total"] >= 1
    assert dashboard["quality"]["total_errors"] >= 1

    realtime = manager.get_realtime_stats()
    assert "last_5_minutes" in realtime
    assert realtime["last_5_minutes"]["api_calls"] >= 2
