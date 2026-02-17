"""add domain tables for contacts, profiles and transfer analytics

Revision ID: 20260215_02
Revises: 20260213_01
Create Date: 2026-02-15 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260215_02"
down_revision = "20260213_01"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("contacts"):
        op.create_table(
            "contacts",
            sa.Column("chat_id", sa.String(), primary_key=True),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("auto_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    if not _table_exists("chat_profiles"):
        op.create_table(
            "chat_profiles",
            sa.Column("chat_id", sa.String(), primary_key=True),
            sa.Column("initial_context", sa.Text(), nullable=True),
            sa.Column("objective", sa.Text(), nullable=True),
            sa.Column("instructions", sa.Text(), nullable=True),
            sa.Column("is_ready", sa.Boolean(), nullable=True, server_default=sa.text("0")),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    if not _table_exists("chat_counters"):
        op.create_table(
            "chat_counters",
            sa.Column("chat_id", sa.String(), primary_key=True),
            sa.Column("assistant_replies_count", sa.Integer(), nullable=True, server_default=sa.text("0")),
            sa.Column("strategy_version", sa.Integer(), nullable=True, server_default=sa.text("0")),
            sa.Column("last_reasoned_at", sa.DateTime(), nullable=True),
        )

    if not _table_exists("chat_strategies"):
        op.create_table(
            "chat_strategies",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("chat_id", sa.String(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=True, server_default=sa.text("1")),
            sa.Column("strategy_text", sa.Text(), nullable=False),
            sa.Column("source_snapshot", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("1")),
        )
        op.create_index("ix_chat_strategies_chat_id", "chat_strategies", ["chat_id"])

    if not _table_exists("silent_transfers"):
        op.create_table(
            "silent_transfers",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("transfer_id", sa.String(length=100), nullable=False),
            sa.Column("chat_id", sa.String(length=200), nullable=False),
            sa.Column("reason", sa.String(length=50), nullable=False),
            sa.Column("trigger_message", sa.Text(), nullable=True),
            sa.Column("conversation_context", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("5")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("assigned_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("assigned_to", sa.String(length=100), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("client_notified", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
        op.create_unique_constraint("uq_silent_transfers_transfer_id", "silent_transfers", ["transfer_id"])
        op.create_index("ix_silent_transfers_transfer_id", "silent_transfers", ["transfer_id"])
        op.create_index("ix_silent_transfers_chat_id", "silent_transfers", ["chat_id"])
        op.create_index("ix_silent_transfers_reason", "silent_transfers", ["reason"])
        op.create_index("ix_silent_transfers_status", "silent_transfers", ["status"])
        op.create_index("ix_silent_transfers_created_at", "silent_transfers", ["created_at"])
        op.create_index("ix_silent_transfers_assigned_to", "silent_transfers", ["assigned_to"])

    if not _table_exists("humanization_metrics"):
        op.create_table(
            "humanization_metrics",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("chat_id", sa.String(length=200), nullable=False),
            sa.Column("session_id", sa.String(length=100), nullable=True),
            sa.Column("bot_suspicion_detected", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("bot_suspicion_triggers", sa.JSON(), nullable=True),
            sa.Column("bot_suspicion_level", sa.Integer(), nullable=True, server_default=sa.text("0")),
            sa.Column("silent_transfers_count", sa.Integer(), nullable=True, server_default=sa.text("0")),
            sa.Column("humanized_responses_count", sa.Integer(), nullable=True, server_default=sa.text("0")),
            sa.Column("simple_question_failures", sa.Integer(), nullable=True, server_default=sa.text("0")),
            sa.Column("ethical_refusals", sa.Integer(), nullable=True, server_default=sa.text("0")),
            sa.Column("bot_revealing_responses", sa.Integer(), nullable=True, server_default=sa.text("0")),
            sa.Column("responses_humanized", sa.Integer(), nullable=True, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_humanization_metrics_chat_id", "humanization_metrics", ["chat_id"])

    if not _table_exists("conversation_objectives"):
        op.create_table(
            "conversation_objectives",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("chat_id", sa.String(length=200), nullable=False),
            sa.Column("session_id", sa.String(length=100), nullable=True),
            sa.Column("global_objective", sa.String(length=100), nullable=True),
            sa.Column("client_objective", sa.Text(), nullable=True),
            sa.Column("objective_achieved", sa.String(length=20), nullable=True),
            sa.Column("conversion_happened", sa.Boolean(), nullable=True, server_default=sa.text("0")),
            sa.Column("initial_emotion", sa.String(length=50), nullable=True),
            sa.Column("final_emotion", sa.String(length=50), nullable=True),
            sa.Column("emotion_trend", sa.String(length=20), nullable=True),
            sa.Column("satisfaction_score", sa.Integer(), nullable=True),
            sa.Column("response_quality_score", sa.Integer(), nullable=True),
            sa.Column("failure_reasons", sa.JSON(), nullable=True),
            sa.Column("success_factors", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_conversation_objectives_chat_id", "conversation_objectives", ["chat_id"])
        op.create_index("ix_conversation_objectives_session_id", "conversation_objectives", ["session_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "conversation_objectives" in tables:
        op.drop_table("conversation_objectives")
    if "humanization_metrics" in tables:
        op.drop_table("humanization_metrics")
    if "silent_transfers" in tables:
        op.drop_table("silent_transfers")
    if "chat_strategies" in tables:
        op.drop_table("chat_strategies")
    if "chat_counters" in tables:
        op.drop_table("chat_counters")
    if "chat_profiles" in tables:
        op.drop_table("chat_profiles")
    if "contacts" in tables:
        op.drop_table("contacts")
