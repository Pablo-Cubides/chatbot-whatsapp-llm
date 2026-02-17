"""add calendar credentials and appointments tables

Revision ID: 20260215_03
Revises: 20260215_02
Create Date: 2026-02-15 01:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260215_03"
down_revision = "20260215_02"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("appointments"):
        op.create_table(
            "appointments",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("appointment_id", sa.String(length=100), nullable=False),
            sa.Column("chat_id", sa.String(length=200), nullable=False),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("start_time", sa.DateTime(), nullable=False),
            sa.Column("end_time", sa.DateTime(), nullable=False),
            sa.Column("timezone", sa.String(length=50), nullable=True, server_default="America/Bogota"),
            sa.Column("location", sa.String(length=500), nullable=True),
            sa.Column("client_name", sa.String(length=200), nullable=False),
            sa.Column("client_email", sa.String(length=200), nullable=True),
            sa.Column("client_phone", sa.String(length=50), nullable=True),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("external_id", sa.String(length=300), nullable=True),
            sa.Column("external_link", sa.String(length=500), nullable=True),
            sa.Column("ical_uid", sa.String(length=300), nullable=True),
            sa.Column("reminder_sent", sa.Boolean(), nullable=True, server_default=sa.text("0")),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        )
        op.create_unique_constraint("uq_appointments_appointment_id", "appointments", ["appointment_id"])
        op.create_index("ix_appointments_appointment_id", "appointments", ["appointment_id"])
        op.create_index("ix_appointments_chat_id", "appointments", ["chat_id"])
        op.create_index("ix_appointments_start_time", "appointments", ["start_time"])
        op.create_index("ix_appointments_provider", "appointments", ["provider"])
        op.create_index("ix_appointments_status", "appointments", ["status"])

    if not _table_exists("calendar_credentials"):
        op.create_table(
            "calendar_credentials",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("access_token", sa.Text(), nullable=True),
            sa.Column("refresh_token", sa.Text(), nullable=True),
            sa.Column("token_type", sa.String(length=50), nullable=True, server_default="Bearer"),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("scope", sa.Text(), nullable=True),
            sa.Column("account_email", sa.String(length=200), nullable=True),
            sa.Column("calendar_id", sa.String(length=300), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("1")),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_unique_constraint("uq_calendar_credentials_provider", "calendar_credentials", ["provider"])
        op.create_index("ix_calendar_credentials_provider", "calendar_credentials", ["provider"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "calendar_credentials" in tables:
        op.drop_table("calendar_credentials")
    if "appointments" in tables:
        op.drop_table("appointments")
