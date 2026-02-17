"""Compatibility shim for legacy imports.

Deprecated: import from `src.models.admin_db` directly.
"""

from src.models.admin_db import (
	ALLOW_CREATE_ALL,
	DATABASE_URL,
	SessionLocal,
	cleanup_connections,
	create_database_engine,
	engine,
	get_db,
	get_db_info,
	get_db_session,
	get_engine,
	get_session,
	initialize_schema,
	migrate_sqlite_to_postgresql,
	test_connection,
)

__all__ = [
	"ALLOW_CREATE_ALL",
	"DATABASE_URL",
	"SessionLocal",
	"cleanup_connections",
	"create_database_engine",
	"engine",
	"get_db",
	"get_db_info",
	"get_db_session",
	"get_engine",
	"get_session",
	"initialize_schema",
	"migrate_sqlite_to_postgresql",
	"test_connection",
]
