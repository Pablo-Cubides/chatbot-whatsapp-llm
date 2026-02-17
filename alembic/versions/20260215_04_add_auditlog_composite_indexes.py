"""add composite indexes for audit log lookups

Revision ID: 20260215_04
Revises: 20260215_03
Create Date: 2026-02-15 00:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260215_04"
down_revision = "20260215_03"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    indexes = inspector.get_indexes(table_name)
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade() -> None:
    # Legacy singular table from SQLAlchemy models.py
    if _table_exists("audit_log"):
        if not _index_exists("audit_log", "ix_audit_log_user_action_ts"):
            op.create_index("ix_audit_log_user_action_ts", "audit_log", ["user_id", "action", "timestamp"])
        if not _index_exists("audit_log", "ix_audit_log_action_ts"):
            op.create_index("ix_audit_log_action_ts", "audit_log", ["action", "timestamp"])

    # Optional plural table from previous migrations for compatibility
    if _table_exists("audit_logs"):
        if not _index_exists("audit_logs", "ix_audit_logs_user_action_ts"):
            op.create_index("ix_audit_logs_user_action_ts", "audit_logs", ["username", "action", "timestamp"])
        if not _index_exists("audit_logs", "ix_audit_logs_action_ts"):
            op.create_index("ix_audit_logs_action_ts", "audit_logs", ["action", "timestamp"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "audit_log" in inspector.get_table_names():
        existing = {idx.get("name") for idx in inspector.get_indexes("audit_log")}
        if "ix_audit_log_action_ts" in existing:
            op.drop_index("ix_audit_log_action_ts", table_name="audit_log")
        if "ix_audit_log_user_action_ts" in existing:
            op.drop_index("ix_audit_log_user_action_ts", table_name="audit_log")

    if "audit_logs" in inspector.get_table_names():
        existing = {idx.get("name") for idx in inspector.get_indexes("audit_logs")}
        if "ix_audit_logs_action_ts" in existing:
            op.drop_index("ix_audit_logs_action_ts", table_name="audit_logs")
        if "ix_audit_logs_user_action_ts" in existing:
            op.drop_index("ix_audit_logs_user_action_ts", table_name="audit_logs")
