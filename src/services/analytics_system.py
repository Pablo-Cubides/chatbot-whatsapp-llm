"""
📊 Sistema de Analytics y Monitoreo
Métricas en tiempo real del chatbot
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class AnalyticsManager:
    def __init__(self, db_path: str = "analytics.db"):
        self.db_path = db_path
        self.init_database()
        self.metrics_cache = {}

    def init_database(self):
        """Inicializar base de datos de analytics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Tabla de métricas generales
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                metric_type TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metadata TEXT
            )
        """)

        # Tabla de conversaciones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_id TEXT,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                ended_at DATETIME,
                message_count INTEGER DEFAULT 0,
                duration_seconds INTEGER,
                satisfaction_score REAL,
                converted BOOLEAN DEFAULT FALSE,
                api_provider TEXT,
                business_config_version TEXT
            )
        """)

        # Tabla de uso de APIs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                api_provider TEXT NOT NULL,
                endpoint TEXT,
                tokens_used INTEGER,
                response_time_ms INTEGER,
                success BOOLEAN,
                error_message TEXT,
                cost_estimate REAL
            )
        """)

        conn.commit()
        conn.close()

    def record_conversation_start(self, session_id: str, user_id: str = None) -> int:
        """Registrar inicio de conversación"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO conversations (session_id, user_id, started_at)
            VALUES (?, ?, ?)
        """,
            (session_id, user_id, datetime.now()),
        )

        conversation_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return conversation_id

    def record_conversation_end(
        self, session_id: str, message_count: int, satisfaction_score: float = None, converted: bool = False
    ):
        """Registrar fin de conversación"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Calcular duración
        cursor.execute(
            """
            SELECT started_at FROM conversations
            WHERE session_id = ? AND ended_at IS NULL
            ORDER BY id DESC LIMIT 1
        """,
            (session_id,),
        )

        result = cursor.fetchone()
        if result:
            start_time = datetime.fromisoformat(result[0])
            duration = (datetime.now() - start_time).total_seconds()

            cursor.execute(
                """
                UPDATE conversations
                SET ended_at = ?, message_count = ?, duration_seconds = ?,
                    satisfaction_score = ?, converted = ?
                WHERE session_id = ? AND ended_at IS NULL
            """,
                (datetime.now(), message_count, duration, satisfaction_score, converted, session_id),
            )

        conn.commit()
        conn.close()

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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO api_usage (api_provider, endpoint, tokens_used, response_time_ms,
                                 success, error_message, cost_estimate)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (api_provider, endpoint, tokens_used, response_time_ms, success, error_message, cost_estimate),
        )

        conn.commit()
        conn.close()

    def record_metric(self, metric_type: str, value: float, metadata: dict = None):
        """Registrar métrica general"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute(
            """
            INSERT INTO metrics (metric_type, metric_value, metadata)
            VALUES (?, ?, ?)
        """,
            (metric_type, value, metadata_json),
        )

        conn.commit()
        conn.close()

    def get_dashboard_metrics(self, hours: int = 24) -> dict[str, Any]:
        """Obtener métricas principales para dashboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = datetime.now() - timedelta(hours=hours)

        # Conversaciones totales
        cursor.execute(
            """
            SELECT COUNT(*) FROM conversations
            WHERE started_at >= ?
        """,
            (since,),
        )
        total_conversations = cursor.fetchone()[0]

        # Conversaciones activas
        cursor.execute(
            """
            SELECT COUNT(*) FROM conversations
            WHERE started_at >= ? AND ended_at IS NULL
        """,
            (since,),
        )
        active_conversations = cursor.fetchone()[0]

        # Mensajes promedio por conversación
        cursor.execute(
            """
            SELECT AVG(message_count) FROM conversations
            WHERE started_at >= ? AND message_count > 0
        """,
            (since,),
        )
        avg_messages = cursor.fetchone()[0] or 0

        # Duración promedio de conversación
        cursor.execute(
            """
            SELECT AVG(duration_seconds) FROM conversations
            WHERE started_at >= ? AND duration_seconds IS NOT NULL
        """,
            (since,),
        )
        avg_duration = cursor.fetchone()[0] or 0

        # Tasa de conversión
        cursor.execute(
            """
            SELECT
                COUNT(CASE WHEN converted THEN 1 END) * 100.0 / COUNT(*) as conversion_rate
            FROM conversations
            WHERE started_at >= ? AND ended_at IS NOT NULL
        """,
            (since,),
        )
        conversion_rate = cursor.fetchone()[0] or 0

        # Uso de APIs por proveedor
        cursor.execute(
            """
            SELECT api_provider, COUNT(*), SUM(tokens_used), AVG(response_time_ms),
                   SUM(CASE WHEN success THEN 0 ELSE 1 END) as errors
            FROM api_usage
            WHERE timestamp >= ?
            GROUP BY api_provider
        """,
            (since,),
        )
        api_usage = cursor.fetchall()

        # Satisfacción promedio
        cursor.execute(
            """
            SELECT AVG(satisfaction_score) FROM conversations
            WHERE started_at >= ? AND satisfaction_score IS NOT NULL
        """,
            (since,),
        )
        avg_satisfaction = cursor.fetchone()[0] or 0

        conn.close()

        return {
            "period_hours": hours,
            "timestamp": datetime.now().isoformat(),
            "conversations": {
                "total": total_conversations,
                "active": active_conversations,
                "avg_messages": round(avg_messages, 2),
                "avg_duration_minutes": round(avg_duration / 60, 2) if avg_duration else 0,
                "conversion_rate": round(conversion_rate, 2),
            },
            "quality": {"avg_satisfaction": round(avg_satisfaction, 2), "total_errors": sum(row[4] for row in api_usage)},
            "api_usage": [
                {
                    "provider": row[0],
                    "requests": row[1],
                    "tokens": row[2] or 0,
                    "avg_response_ms": round(row[3], 2) if row[3] else 0,
                    "errors": row[4],
                }
                for row in api_usage
            ],
        }

    def get_time_series_data(self, metric: str, hours: int = 24, interval_minutes: int = 60) -> list[dict]:
        """Obtener datos de serie temporal para gráficos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = datetime.now() - timedelta(hours=hours)

        if metric == "conversations":
            cursor.execute(
                """
                SELECT
                    datetime(started_at, 'localtime') as hour,
                    COUNT(*) as count
                FROM conversations
                WHERE started_at >= ?
                GROUP BY strftime('%Y-%m-%d %H', started_at)
                ORDER BY hour
            """,
                (since,),
            )

        elif metric == "api_calls":
            cursor.execute(
                """
                SELECT
                    datetime(timestamp, 'localtime') as hour,
                    COUNT(*) as count
                FROM api_usage
                WHERE timestamp >= ?
                GROUP BY strftime('%Y-%m-%d %H', timestamp)
                ORDER BY hour
            """,
                (since,),
            )

        elif metric == "errors":
            cursor.execute(
                """
                SELECT
                    datetime(timestamp, 'localtime') as hour,
                    COUNT(*) as count
                FROM api_usage
                WHERE timestamp >= ? AND success = 0
                GROUP BY strftime('%Y-%m-%d %H', timestamp)
                ORDER BY hour
            """,
                (since,),
            )

        data = cursor.fetchall()
        conn.close()

        return [{"timestamp": row[0], "value": row[1]} for row in data]

    def get_realtime_stats(self) -> dict[str, Any]:
        """Estadísticas en tiempo real"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Últimas 5 minutos
        recent = datetime.now() - timedelta(minutes=5)

        cursor.execute(
            """
            SELECT COUNT(*) FROM api_usage WHERE timestamp >= ?
        """,
            (recent,),
        )
        recent_api_calls = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM conversations WHERE started_at >= ?
        """,
            (recent,),
        )
        recent_conversations = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM api_usage WHERE timestamp >= ? AND success = 0
        """,
            (recent,),
        )
        recent_errors = cursor.fetchone()[0]

        conn.close()

        return {
            "timestamp": datetime.now().isoformat(),
            "last_5_minutes": {
                "api_calls": recent_api_calls,
                "new_conversations": recent_conversations,
                "errors": recent_errors,
            },
        }


# Instancia global
analytics_manager = AnalyticsManager()
