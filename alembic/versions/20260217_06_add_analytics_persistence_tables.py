"""add persistent analytics tables

Revision ID: 20260217_06
Revises: 20260215_05
Create Date: 2026-02-17 10:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260217_06"
down_revision = "20260215_05"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    indexes = _inspector().get_indexes(table_name)
    return any(i.get("name") == index_name for i in indexes)


def upgrade() -> None:
    if not _table_exists("analytics_metrics"):
        op.create_table(
            "analytics_metrics",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("metric_type", sa.String(length=100), nullable=False),
            sa.Column("metric_value", sa.Float(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=True),
        )
    if not _index_exists("analytics_metrics", "ix_analytics_metrics_timestamp"):
        op.create_index("ix_analytics_metrics_timestamp", "analytics_metrics", ["timestamp"])
    if not _index_exists("analytics_metrics", "ix_analytics_metrics_metric_type"):
        op.create_index("ix_analytics_metrics_metric_type", "analytics_metrics", ["metric_type"])

    if not _table_exists("analytics_conversations"):
        op.create_table(
            "analytics_conversations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("session_id", sa.String(length=120), nullable=False),
            sa.Column("user_id", sa.String(length=120), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("ended_at", sa.DateTime(), nullable=True),
            sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duration_seconds", sa.Integer(), nullable=True),
            sa.Column("satisfaction_score", sa.Float(), nullable=True),
            sa.Column("converted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("api_provider", sa.String(length=80), nullable=True),
            sa.Column("business_config_version", sa.String(length=120), nullable=True),
        )
    for index_name, cols in [
        ("ix_analytics_conversations_session_id", ["session_id"]),
        ("ix_analytics_conversations_user_id", ["user_id"]),
        ("ix_analytics_conversations_started_at", ["started_at"]),
        ("ix_analytics_conversations_ended_at", ["ended_at"]),
        ("ix_analytics_conversations_converted", ["converted"]),
        ("ix_analytics_conversations_api_provider", ["api_provider"]),
    ]:
        if not _index_exists("analytics_conversations", index_name):
            op.create_index(index_name, "analytics_conversations", cols)

    if not _table_exists("analytics_api_usage"):
        op.create_table(
            "analytics_api_usage",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("api_provider", sa.String(length=80), nullable=False),
            sa.Column("endpoint", sa.String(length=255), nullable=True),
            sa.Column("tokens_used", sa.Integer(), nullable=True),
            sa.Column("response_time_ms", sa.Integer(), nullable=True),
            sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("cost_estimate", sa.Float(), nullable=True),
        )
    for index_name, cols in [
        ("ix_analytics_api_usage_timestamp", ["timestamp"]),
        ("ix_analytics_api_usage_api_provider", ["api_provider"]),
        ("ix_analytics_api_usage_success", ["success"]),
    ]:
        if not _index_exists("analytics_api_usage", index_name):
            op.create_index(index_name, "analytics_api_usage", cols)


def downgrade() -> None:
    for table_name in ["analytics_api_usage", "analytics_conversations", "analytics_metrics"]:
        if _table_exists(table_name):
            op.drop_table(table_name)
