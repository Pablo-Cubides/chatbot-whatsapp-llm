import pytest

from src.services.realtime_metrics import RealtimeMetricsManager

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("times", "expected_bucket"),
    [([0.2], "0-1s"), ([1.2], "1-3s"), ([3.2], "3-5s"), ([5.5], "5-10s"), ([12.0], "10s+")],
)
def test_response_time_distribution_buckets(times, expected_bucket) -> None:
    manager = RealtimeMetricsManager()
    payload = [{"time": t, "timestamp": None} for t in times]
    distribution = manager._get_response_time_distribution(payload)

    assert distribution[expected_bucket] == len(times)


def test_cleanup_old_metrics_removes_stale_entries() -> None:
    from datetime import datetime, timedelta

    manager = RealtimeMetricsManager()
    old = datetime.now() - timedelta(hours=30)
    manager.metrics_cache["conversations"][old.replace(minute=0, second=0, microsecond=0)] = 2
    manager.metrics_cache["messages"][old.replace(minute=0, second=0, microsecond=0)] = 3
    manager.metrics_cache["errors"][old.replace(minute=0, second=0, microsecond=0)] = 1
    manager.metrics_cache["humanization_events"][f"{old.isoformat()}_transfer"] = 1

    manager.cleanup_old_metrics()

    assert not manager.metrics_cache["conversations"]
    assert not manager.metrics_cache["messages"]
    assert not manager.metrics_cache["errors"]
    assert not manager.metrics_cache["humanization_events"]
