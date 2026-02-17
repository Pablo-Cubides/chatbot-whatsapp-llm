"""Phase 5C infrastructure/data contracts for DB model layer."""

from __future__ import annotations

import pytest

from src.models import admin_db
from src.models.models import Base

pytestmark = pytest.mark.unit



def test_model_metadata_contains_critical_phase5_tables() -> None:
    expected_tables = {
        "appointments",
        "contacts",
        "conversation_messages",
        "business_configs",
        "prompts",
    }

    available = set(Base.metadata.tables.keys())
    missing = expected_tables - available
    assert not missing, f"Missing tables: {missing}"



def test_appointment_table_columns_contract() -> None:
    table = Base.metadata.tables["appointments"]
    expected_columns = {
        "appointment_id",
        "chat_id",
        "start_time",
        "end_time",
        "client_name",
        "provider",
        "status",
        "external_id",
        "external_link",
        "created_at",
        "updated_at",
    }

    available_columns = set(table.columns.keys())
    assert expected_columns.issubset(available_columns)



def test_contacts_phone_unique_index_contract() -> None:
    table = Base.metadata.tables["contacts"]
    assert any(index.unique and "phone" in [column.name for column in index.columns] for index in table.indexes)



def test_database_info_contract_shape() -> None:
    info = admin_db.get_db_info()

    assert "type" in info
    assert "url" in info
    assert "connected" in info
    assert isinstance(info.get("connected"), bool)
