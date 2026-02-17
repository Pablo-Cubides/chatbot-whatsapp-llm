"""initial core tables

Revision ID: 20260213_01
Revises:
Create Date: 2026-02-13 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260213_01"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("username", sa.String(length=100), nullable=False),
            sa.Column("role", sa.String(length=50), nullable=False),
            sa.Column("action", sa.String(length=100), nullable=False),
            sa.Column("resource", sa.String(length=200), nullable=True),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("success", sa.String(length=10), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
        )
        op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
        op.create_index("ix_audit_logs_username", "audit_logs", ["username"])
        op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
        op.create_index("ix_audit_logs_resource", "audit_logs", ["resource"])

    if not _table_exists("alert_rules"):
        op.create_table(
            "alert_rules",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("rule_type", sa.String(length=50), nullable=False),
            sa.Column("pattern", sa.Text(), nullable=True),
            sa.Column("severity", sa.String(length=20), nullable=False),
            sa.Column("actions", sa.JSON(), nullable=False),
            sa.Column("schedule", sa.JSON(), nullable=True),
            sa.Column("extra_data", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.String(length=100), nullable=False),
        )
        op.create_index("ix_alert_rules_rule_type", "alert_rules", ["rule_type"])

    if not _table_exists("alerts"):
        op.create_table(
            "alerts",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("alert_id", sa.String(length=100), nullable=False),
            sa.Column("rule_id", sa.Integer(), nullable=True),
            sa.Column("chat_id", sa.String(length=200), nullable=False),
            sa.Column("message_text", sa.Text(), nullable=True),
            sa.Column("severity", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("assigned_to", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("extra_data", sa.JSON(), nullable=True),
        )
        op.create_unique_constraint("uq_alerts_alert_id", "alerts", ["alert_id"])
        op.create_index("ix_alerts_alert_id", "alerts", ["alert_id"])
        op.create_index("ix_alerts_rule_id", "alerts", ["rule_id"])
        op.create_index("ix_alerts_chat_id", "alerts", ["chat_id"])
        op.create_index("ix_alerts_severity", "alerts", ["severity"])
        op.create_index("ix_alerts_status", "alerts", ["status"])
        op.create_index("ix_alerts_assigned_to", "alerts", ["assigned_to"])
        op.create_index("ix_alerts_created_at", "alerts", ["created_at"])

    if not _table_exists("message_queue"):
        op.create_table(
            "message_queue",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("message_id", sa.String(length=100), nullable=False),
            sa.Column("chat_id", sa.String(length=200), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("priority", sa.Integer(), nullable=False),
            sa.Column("scheduled_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=False),
            sa.Column("max_retries", sa.Integer(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("extra_data", sa.JSON(), nullable=True),
        )
        op.create_unique_constraint("uq_message_queue_message_id", "message_queue", ["message_id"])
        op.create_index("ix_message_queue_message_id", "message_queue", ["message_id"])
        op.create_index("ix_message_queue_chat_id", "message_queue", ["chat_id"])
        op.create_index("ix_message_queue_status", "message_queue", ["status"])
        op.create_index("ix_message_queue_scheduled_at", "message_queue", ["scheduled_at"])

    if not _table_exists("campaigns"):
        op.create_table(
            "campaigns",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("campaign_id", sa.String(length=100), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_by", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("total_messages", sa.Integer(), nullable=False),
            sa.Column("sent_messages", sa.Integer(), nullable=False),
            sa.Column("failed_messages", sa.Integer(), nullable=False),
            sa.Column("extra_data", sa.JSON(), nullable=True),
        )
        op.create_unique_constraint("uq_campaigns_campaign_id", "campaigns", ["campaign_id"])
        op.create_index("ix_campaigns_campaign_id", "campaigns", ["campaign_id"])
        op.create_index("ix_campaigns_status", "campaigns", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "campaigns" in tables:
        op.drop_table("campaigns")
    if "message_queue" in tables:
        op.drop_table("message_queue")
    if "alerts" in tables:
        op.drop_table("alerts")
    if "alert_rules" in tables:
        op.drop_table("alert_rules")
    if "audit_logs" in tables:
        op.drop_table("audit_logs")
