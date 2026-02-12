"""
Metrics collection and /metrics endpoint.
Provides Prometheus-compatible metrics for monitoring.
"""

import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Response

router = APIRouter(tags=["monitoring"])

# ═══════════════════════ Counters & Gauges ═══════════════════════

_lock = threading.Lock()

_counters: dict[str, int] = defaultdict(int)
_histograms: dict[str, list] = defaultdict(list)
_gauges: dict[str, float] = {}
_start_time = time.monotonic()

# Maximum histogram samples to keep per metric (sliding window)
_MAX_HISTOGRAM_SAMPLES = 1000


def inc_counter(name: str, amount: int = 1) -> None:
    """Increment a counter metric."""
    with _lock:
        _counters[name] += amount


def observe_histogram(name: str, value: float) -> None:
    """Record a histogram observation (e.g., latency)."""
    with _lock:
        samples = _histograms[name]
        samples.append(value)
        if len(samples) > _MAX_HISTOGRAM_SAMPLES:
            _histograms[name] = samples[-_MAX_HISTOGRAM_SAMPLES:]


def set_gauge(name: str, value: float) -> None:
    """Set a gauge metric to a specific value."""
    with _lock:
        _gauges[name] = value


def get_metrics_snapshot() -> dict[str, Any]:
    """Return a snapshot of all current metrics."""
    with _lock:
        uptime = time.monotonic() - _start_time

        histogram_stats = {}
        for name, samples in _histograms.items():
            if samples:
                sorted_s = sorted(samples)
                n = len(sorted_s)
                histogram_stats[name] = {
                    "count": n,
                    "sum": sum(sorted_s),
                    "avg": sum(sorted_s) / n,
                    "p50": sorted_s[n // 2],
                    "p95": sorted_s[int(n * 0.95)] if n >= 20 else sorted_s[-1],
                    "p99": sorted_s[int(n * 0.99)] if n >= 100 else sorted_s[-1],
                    "max": sorted_s[-1],
                }

        return {
            "uptime_seconds": round(uptime, 1),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "counters": dict(_counters),
            "gauges": dict(_gauges),
            "histograms": histogram_stats,
        }


# ═══════════════════════ Prometheus Text Format ═══════════════════════


def _prometheus_text() -> str:
    """Render metrics in Prometheus text exposition format."""
    lines = []
    snapshot = get_metrics_snapshot()

    lines.append("# HELP uptime_seconds Seconds since process start")
    lines.append("# TYPE uptime_seconds gauge")
    lines.append(f"uptime_seconds {snapshot['uptime_seconds']}")

    for name, value in snapshot["counters"].items():
        safe = name.replace(".", "_").replace("-", "_")
        lines.append(f"# TYPE {safe}_total counter")
        lines.append(f"{safe}_total {value}")

    for name, value in snapshot["gauges"].items():
        safe = name.replace(".", "_").replace("-", "_")
        lines.append(f"# TYPE {safe} gauge")
        lines.append(f"{safe} {value}")

    for name, stats in snapshot["histograms"].items():
        safe = name.replace(".", "_").replace("-", "_")
        lines.append(f"# TYPE {safe} summary")
        lines.append(f"{safe}_count {stats['count']}")
        lines.append(f"{safe}_sum {stats['sum']:.4f}")
        lines.append(f'{safe}{{quantile="0.5"}} {stats["p50"]:.4f}')
        lines.append(f'{safe}{{quantile="0.95"}} {stats["p95"]:.4f}')
        lines.append(f'{safe}{{quantile="0.99"}} {stats["p99"]:.4f}')

    return "\n".join(lines) + "\n"


# ═══════════════════════ API Endpoints ═══════════════════════


@router.get("/metrics")
async def metrics_endpoint():
    """Prometheus-compatible /metrics endpoint."""
    body = _prometheus_text()
    return Response(
        content=body,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/metrics/json")
async def metrics_json():
    """JSON metrics endpoint for dashboards."""
    return get_metrics_snapshot()
