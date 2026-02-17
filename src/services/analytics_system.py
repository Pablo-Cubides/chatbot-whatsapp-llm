"""
📊 Sistema de Analytics y Monitoreo
Métricas en tiempo real del chatbot
"""

import json
import logging
import os
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.admin_db import SessionLocal
from src.models.models import AnalyticsApiUsage, AnalyticsConversation, AnalyticsMetric, Base

logger = logging.getLogger(__name__)


class AnalyticsManager:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path
        self.metrics_cache = {}
        self._is_local_sqlite = bool(db_path)

        if self._is_local_sqlite:
            sqlite_path = os.path.abspath(db_path or "analytics.db")
            self._engine = create_engine(
                f"sqlite:///{sqlite_path}",
                connect_args={"check_same_thread": False},
            )
            self._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=self._engine)
            self.init_database()
        else:
            self._engine = None
            self._session_factory = SessionLocal

    def init_database(self):
        """Inicializar esquema para pruebas locales con SQLite."""
        if self._is_local_sqlite and self._engine is not None:
            Base.metadata.create_all(
                bind=self._engine,
                tables=[
                    AnalyticsMetric.__table__,
                    AnalyticsConversation.__table__,
                    AnalyticsApiUsage.__table__,
                ],
            )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_dt(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @contextmanager
    def _session_scope(self):
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def record_conversation_start(self, session_id: str, user_id: str = None) -> int:
        """Registrar inicio de conversación"""
        with self._session_scope() as session:
            row = AnalyticsConversation(
                session_id=session_id,
                user_id=user_id,
                started_at=self._now(),
            )
            session.add(row)
            session.flush()
            return int(row.id or 0)

    def record_conversation_end(
        self, session_id: str, message_count: int, satisfaction_score: float = None, converted: bool = False
    ):
        """Registrar fin de conversación"""
        with self._session_scope() as session:
            conversation = (
                session.query(AnalyticsConversation)
                .filter(AnalyticsConversation.session_id == session_id, AnalyticsConversation.ended_at.is_(None))
                .order_by(AnalyticsConversation.id.desc())
                .first()
            )

            if not conversation:
                return

            now = self._now()
            start_time = self._normalize_dt(conversation.started_at) or now
            duration = int(max(0, (now - start_time).total_seconds()))

            conversation.ended_at = now
            conversation.message_count = int(message_count)
            conversation.duration_seconds = duration
            conversation.satisfaction_score = float(satisfaction_score) if satisfaction_score is not None else None
            conversation.converted = bool(converted)

    def record_api_usage(
        self,
        api_provider: str,
        endpoint: str,
        tokens_used: int,
        response_time_ms: int,
        success: bool = True,
        error_message: str = None,
        cost_estimate: float = None,
    ):
        """Registrar uso de API"""
        with self._session_scope() as session:
            session.add(
                AnalyticsApiUsage(
                    timestamp=self._now(),
                    api_provider=api_provider,
                    endpoint=endpoint,
                    tokens_used=tokens_used,
                    response_time_ms=response_time_ms,
                    success=bool(success),
                    error_message=error_message,
                    cost_estimate=cost_estimate,
                )
            )

    def record_metric(self, metric_type: str, value: float, metadata: dict = None):
        """Registrar métrica general"""
        with self._session_scope() as session:
            session.add(
                AnalyticsMetric(
                    timestamp=self._now(),
                    metric_type=metric_type,
                    metric_value=float(value),
                    metric_metadata=metadata if metadata else None,
                )
            )

    def get_dashboard_metrics(self, hours: int = 24) -> dict[str, Any]:
        """Obtener métricas principales para dashboard"""
        since = self._now() - timedelta(hours=hours)

        with self._session_scope() as session:
            conv_rows = (
                session.query(AnalyticsConversation)
                .filter(AnalyticsConversation.started_at >= since)
                .all()
            )
            api_rows = (
                session.query(AnalyticsApiUsage)
                .filter(AnalyticsApiUsage.timestamp >= since)
                .all()
            )

            total_conversations = len(conv_rows)
            active_conversations = sum(1 for c in conv_rows if c.ended_at is None)

            completed = [c for c in conv_rows if c.ended_at is not None]
            avg_messages = (
                sum(max(0, int(c.message_count or 0)) for c in conv_rows) / total_conversations if total_conversations else 0
            )

            duration_values = [int(c.duration_seconds) for c in conv_rows if c.duration_seconds is not None]
            avg_duration = sum(duration_values) / len(duration_values) if duration_values else 0

            converted_count = sum(1 for c in completed if c.converted)
            conversion_rate = (converted_count * 100.0 / len(completed)) if completed else 0

            satisfaction_values = [float(c.satisfaction_score) for c in conv_rows if c.satisfaction_score is not None]
            avg_satisfaction = sum(satisfaction_values) / len(satisfaction_values) if satisfaction_values else 0

            grouped_usage: dict[str, dict[str, float | int]] = defaultdict(
                lambda: {"requests": 0, "tokens": 0, "response_sum": 0, "response_count": 0, "errors": 0}
            )
            for row in api_rows:
                key = row.api_provider or "unknown"
                bucket = grouped_usage[key]
                bucket["requests"] = int(bucket["requests"]) + 1
                bucket["tokens"] = int(bucket["tokens"]) + int(row.tokens_used or 0)
                if row.response_time_ms is not None:
                    bucket["response_sum"] = float(bucket["response_sum"]) + float(row.response_time_ms)
                    bucket["response_count"] = int(bucket["response_count"]) + 1
                if not bool(row.success):
                    bucket["errors"] = int(bucket["errors"]) + 1

            api_usage = []
            for provider, stats in grouped_usage.items():
                response_count = int(stats["response_count"])
                avg_response = (float(stats["response_sum"]) / response_count) if response_count else 0
                api_usage.append(
                    {
                        "provider": provider,
                        "requests": int(stats["requests"]),
                        "tokens": int(stats["tokens"]),
                        "avg_response_ms": round(avg_response, 2),
                        "errors": int(stats["errors"]),
                    }
                )

        return {
            "period_hours": hours,
            "timestamp": self._now().isoformat(),
            "conversations": {
                "total": total_conversations,
                "active": active_conversations,
                "avg_messages": round(avg_messages, 2),
                "avg_duration_minutes": round(avg_duration / 60, 2) if avg_duration else 0,
                "conversion_rate": round(conversion_rate, 2),
            },
            "quality": {
                "avg_satisfaction": round(avg_satisfaction, 2),
                "total_errors": sum(item["errors"] for item in api_usage),
            },
            "api_usage": api_usage,
        }

    def get_time_series_data(self, metric: str, hours: int = 24, interval_minutes: int = 60) -> list[dict]:
        """Obtener datos de serie temporal para gráficos"""
        safe_hours = max(1, int(hours or 1))
        safe_interval = max(1, int(interval_minutes or 60))
        interval_seconds = safe_interval * 60

        now = self._now().replace(second=0, microsecond=0)
        since = now - timedelta(hours=safe_hours)
        buckets: dict[datetime, int] = defaultdict(int)

        with self._session_scope() as session:
            if metric == "conversations":
                rows = (
                    session.query(AnalyticsConversation.started_at)
                    .filter(AnalyticsConversation.started_at >= since)
                    .all()
                )
                timestamps = [self._normalize_dt(row[0]) for row in rows]
            elif metric == "errors":
                rows = (
                    session.query(AnalyticsApiUsage.timestamp)
                    .filter(AnalyticsApiUsage.timestamp >= since, AnalyticsApiUsage.success.is_(False))
                    .all()
                )
                timestamps = [self._normalize_dt(row[0]) for row in rows]
            else:
                rows = (
                    session.query(AnalyticsApiUsage.timestamp)
                    .filter(AnalyticsApiUsage.timestamp >= since)
                    .all()
                )
                timestamps = [self._normalize_dt(row[0]) for row in rows]

        for ts in timestamps:
            if ts is None:
                continue
            delta_seconds = int((ts - since).total_seconds())
            bucket_offset = max(0, delta_seconds // interval_seconds)
            bucket_time = since + timedelta(seconds=bucket_offset * interval_seconds)
            buckets[bucket_time] += 1

        points: list[dict[str, Any]] = []
        total_buckets = int((safe_hours * 3600) // interval_seconds) + 1
        for idx in range(total_buckets):
            ts = since + timedelta(seconds=idx * interval_seconds)
            points.append({"timestamp": ts.isoformat(), "value": buckets.get(ts, 0)})

        return points

    def get_realtime_stats(self) -> dict[str, Any]:
        """Estadísticas en tiempo real"""
        recent = self._now() - timedelta(minutes=5)

        with self._session_scope() as session:
            recent_api_calls = (
                session.query(AnalyticsApiUsage)
                .filter(AnalyticsApiUsage.timestamp >= recent)
                .count()
            )
            recent_conversations = (
                session.query(AnalyticsConversation)
                .filter(AnalyticsConversation.started_at >= recent)
                .count()
            )
            recent_errors = (
                session.query(AnalyticsApiUsage)
                .filter(AnalyticsApiUsage.timestamp >= recent, AnalyticsApiUsage.success.is_(False))
                .count()
            )

        return {
            "timestamp": self._now().isoformat(),
            "last_5_minutes": {
                "api_calls": recent_api_calls,
                "new_conversations": recent_conversations,
                "errors": recent_errors,
            },
        }


# Instancia global
analytics_manager = AnalyticsManager()
