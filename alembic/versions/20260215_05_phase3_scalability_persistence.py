"""phase 3 scalability, persistence and db hardening

Revision ID: 20260215_05
Revises: 20260215_04
Create Date: 2026-02-15 02:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260215_05"
down_revision = "20260215_04"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    cols = _inspector().get_columns(table_name)
    return any(c.get("name") == column_name for c in cols)


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    indexes = _inspector().get_indexes(table_name)
    return any(i.get("name") == index_name for i in indexes)


def _fk_exists(table_name: str, fk_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    fks = _inspector().get_foreign_keys(table_name)
    return any(fk.get("name") == fk_name for fk in fks)


def upgrade() -> None:
    # contacts.phone + index
    if _table_exists("contacts") and not _column_exists("contacts", "phone"):
        with op.batch_alter_table("contacts") as batch_op:
            batch_op.add_column(sa.Column("phone", sa.String(length=50), nullable=True))

    if _table_exists("contacts") and not _index_exists("contacts", "ix_contacts_phone"):
        op.create_index("ix_contacts_phone", "contacts", ["phone"], unique=True)

    # appointments.contact_phone + FK
    if _table_exists("appointments") and not _column_exists("appointments", "contact_phone"):
        with op.batch_alter_table("appointments") as batch_op:
            batch_op.add_column(sa.Column("contact_phone", sa.String(length=50), nullable=True))

    if _table_exists("appointments") and not _index_exists("appointments", "ix_appointments_contact_phone"):
        op.create_index("ix_appointments_contact_phone", "appointments", ["contact_phone"])

    if _table_exists("appointments") and _table_exists("contacts") and not _fk_exists("appointments", "fk_appointments_contact_phone_contacts"):
        with op.batch_alter_table("appointments") as batch_op:
            batch_op.create_foreign_key(
                "fk_appointments_contact_phone_contacts",
                "contacts",
                ["contact_phone"],
                ["phone"],
            )

    # Composite indexes
    if _table_exists("appointments") and not _index_exists("appointments", "ix_appointment_date_status"):
        op.create_index("ix_appointment_date_status", "appointments", ["start_time", "status"])

    if _table_exists("message_queue") and not _index_exists("message_queue", "ix_queued_message_status_scheduled"):
        op.create_index("ix_queued_message_status_scheduled", "message_queue", ["status", "scheduled_at"])

    # conversation_messages table
    if not _table_exists("conversation_messages"):
        op.create_table(
            "conversation_messages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("session_id", sa.String(length=120), nullable=False),
            sa.Column("chat_id", sa.String(length=200), nullable=False),
            sa.Column("phone", sa.String(length=50), nullable=True),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_conversation_messages_session_id", "conversation_messages", ["session_id"])
        op.create_index("ix_conversation_messages_chat_id", "conversation_messages", ["chat_id"])
        op.create_index("ix_conversation_messages_phone", "conversation_messages", ["phone"])
        op.create_index("ix_conversation_messages_created_at", "conversation_messages", ["created_at"])

    if _table_exists("conversation_messages") and _table_exists("contacts") and not _fk_exists("conversation_messages", "fk_conversation_messages_phone_contacts"):
        with op.batch_alter_table("conversation_messages") as batch_op:
            batch_op.create_foreign_key(
                "fk_conversation_messages_phone_contacts",
                "contacts",
                ["phone"],
                ["phone"],
            )

    # business_configs + prompts with updated_at
    if not _table_exists("business_configs"):
        op.create_table(
            "business_configs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("key", sa.String(length=120), nullable=False),
            sa.Column("value", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_business_configs_key", "business_configs", ["key"], unique=True)

    if not _table_exists("prompts"):
        op.create_table(
            "prompts",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("key", sa.String(length=120), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_prompts_key", "prompts", ["key"], unique=True)

    # A/B testing persistence tables
    if not _table_exists("ab_experiments"):
        op.create_table(
            "ab_experiments",
            sa.Column("id", sa.String(length=120), primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("variant_type", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("success_metric", sa.String(length=50), nullable=False),
            sa.Column("min_sample_size", sa.Integer(), nullable=False),
            sa.Column("confidence_level", sa.Float(), nullable=False),
            sa.Column("total_participants", sa.Integer(), nullable=False),
            sa.Column("winner_variant_id", sa.String(length=120), nullable=True),
            sa.Column("is_statistically_significant", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("ended_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_ab_experiments_status", "ab_experiments", ["status"])
        op.create_index("ix_ab_experiments_variant_type", "ab_experiments", ["variant_type"])

    if not _table_exists("ab_variants"):
        op.create_table(
            "ab_variants",
            sa.Column("id", sa.String(length=120), primary_key=True),
            sa.Column("experiment_id", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("config", sa.JSON(), nullable=False),
            sa.Column("traffic_percentage", sa.Float(), nullable=False),
            sa.Column("total_conversations", sa.Integer(), nullable=False),
            sa.Column("successful_conversations", sa.Integer(), nullable=False),
            sa.Column("avg_response_time", sa.Float(), nullable=False),
            sa.Column("avg_satisfaction_score", sa.Float(), nullable=False),
            sa.Column("bot_suspicions", sa.Integer(), nullable=False),
            sa.Column("objectives_achieved", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["experiment_id"], ["ab_experiments.id"], name="fk_ab_variants_experiment"),
        )
        op.create_index("ix_ab_variants_experiment_id", "ab_variants", ["experiment_id"])

    if not _table_exists("ab_assignments"):
        op.create_table(
            "ab_assignments",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("contact", sa.String(length=200), nullable=False),
            sa.Column("experiment_id", sa.String(length=120), nullable=False),
            sa.Column("variant_id", sa.String(length=120), nullable=False),
            sa.Column("assigned_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["experiment_id"], ["ab_experiments.id"], name="fk_ab_assignments_experiment"),
            sa.ForeignKeyConstraint(["variant_id"], ["ab_variants.id"], name="fk_ab_assignments_variant"),
        )
        op.create_index("ix_ab_assignments_contact", "ab_assignments", ["contact"])
        op.create_index("ix_ab_assignments_experiment_id", "ab_assignments", ["experiment_id"])
        op.create_index("ix_ab_assignments_variant_id", "ab_assignments", ["variant_id"])
        op.create_index("ix_ab_assignments_contact_experiment", "ab_assignments", ["contact", "experiment_id"], unique=True)

    if not _table_exists("ab_results"):
        op.create_table(
            "ab_results",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("contact", sa.String(length=200), nullable=False),
            sa.Column("experiment_id", sa.String(length=120), nullable=False),
            sa.Column("variant_id", sa.String(length=120), nullable=False),
            sa.Column("success", sa.Boolean(), nullable=False),
            sa.Column("response_time", sa.Float(), nullable=False),
            sa.Column("satisfaction_score", sa.Float(), nullable=False),
            sa.Column("bot_suspicion", sa.Boolean(), nullable=False),
            sa.Column("objective_achieved", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["experiment_id"], ["ab_experiments.id"], name="fk_ab_results_experiment"),
            sa.ForeignKeyConstraint(["variant_id"], ["ab_variants.id"], name="fk_ab_results_variant"),
        )
        op.create_index("ix_ab_results_contact", "ab_results", ["contact"])
        op.create_index("ix_ab_results_experiment_id", "ab_results", ["experiment_id"])
        op.create_index("ix_ab_results_variant_id", "ab_results", ["variant_id"])
        op.create_index("ix_ab_results_created_at", "ab_results", ["created_at"])

    # Deep analyzer persistent profiles
    if not _table_exists("conversation_profiles"):
        op.create_table(
            "conversation_profiles",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("session_id", sa.String(length=120), nullable=False),
            sa.Column("contact", sa.String(length=200), nullable=False),
            sa.Column("primary_emotion", sa.String(length=50), nullable=False),
            sa.Column("emotion_confidence", sa.Float(), nullable=False),
            sa.Column("objective_status", sa.String(length=50), nullable=False),
            sa.Column("objective_name", sa.String(length=255), nullable=True),
            sa.Column("conversation_quality_score", sa.Float(), nullable=False),
            sa.Column("response_naturalness_score", sa.Float(), nullable=False),
            sa.Column("customer_satisfaction_score", sa.Float(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("analyzed_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_conversation_profiles_session_id", "conversation_profiles", ["session_id"])
        op.create_index("ix_conversation_profiles_contact", "conversation_profiles", ["contact"])
        op.create_index("ix_conversation_profiles_analyzed_at", "conversation_profiles", ["analyzed_at"])


def downgrade() -> None:
    if _table_exists("conversation_profiles"):
        op.drop_table("conversation_profiles")

    if _table_exists("ab_results"):
        op.drop_table("ab_results")
    if _table_exists("ab_assignments"):
        op.drop_table("ab_assignments")
    if _table_exists("ab_variants"):
        op.drop_table("ab_variants")
    if _table_exists("ab_experiments"):
        op.drop_table("ab_experiments")

    if _table_exists("prompts"):
        op.drop_table("prompts")
    if _table_exists("business_configs"):
        op.drop_table("business_configs")

    if _table_exists("conversation_messages"):
        op.drop_table("conversation_messages")

    if _table_exists("message_queue") and _index_exists("message_queue", "ix_queued_message_status_scheduled"):
        op.drop_index("ix_queued_message_status_scheduled", table_name="message_queue")

    if _table_exists("appointments") and _index_exists("appointments", "ix_appointment_date_status"):
        op.drop_index("ix_appointment_date_status", table_name="appointments")

    if _table_exists("appointments") and _fk_exists("appointments", "fk_appointments_contact_phone_contacts"):
        with op.batch_alter_table("appointments") as batch_op:
            batch_op.drop_constraint("fk_appointments_contact_phone_contacts", type_="foreignkey")

    if _table_exists("appointments") and _index_exists("appointments", "ix_appointments_contact_phone"):
        op.drop_index("ix_appointments_contact_phone", table_name="appointments")

    if _table_exists("appointments") and _column_exists("appointments", "contact_phone"):
        with op.batch_alter_table("appointments") as batch_op:
            batch_op.drop_column("contact_phone")

    if _table_exists("contacts") and _index_exists("contacts", "ix_contacts_phone"):
        op.drop_index("ix_contacts_phone", table_name="contacts")

    if _table_exists("contacts") and _column_exists("contacts", "phone"):
        with op.batch_alter_table("contacts") as batch_op:
            batch_op.drop_column("phone")
