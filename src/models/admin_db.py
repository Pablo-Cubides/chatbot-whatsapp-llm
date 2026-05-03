"""
Sistema de base de datos mejorado con soporte para PostgreSQL y SQLite
Pool de conexiones y configuración optimizada para producción
"""

import atexit
import logging
import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from src.models.models import Base

logger = logging.getLogger(__name__)

# Configuración de base de datos desde variables de entorno
DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite:///chatbot_context.db"
ALLOW_CREATE_ALL = os.getenv("DB_ALLOW_CREATE_ALL", "false").lower() == "true"


def create_database_engine():
    """Crear engine de base de datos con configuración optimizada"""
    sql_echo = os.getenv("SQL_ECHO", "false").lower() == "true"

    if DATABASE_URL.startswith("sqlite"):
        # Configuración para SQLite
        sqlite_timeout = int(os.getenv("SQLITE_TIMEOUT_SECONDS", "20") or "20")
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False, "timeout": sqlite_timeout},
            poolclass=StaticPool,
            echo=sql_echo,
        )
        logger.info("🗃️ Configurando SQLite database")

    elif DATABASE_URL.startswith("postgresql"):
        # Configuración para PostgreSQL
        pool_size = int(os.getenv("DB_POOL_SIZE", "20") or "20")
        max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "30") or "30")
        pool_recycle = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "3600") or "3600")
        pool_timeout = int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "30") or "30")
        engine = create_engine(
            DATABASE_URL,
            poolclass=QueuePool,
            pool_size=max(1, pool_size),
            max_overflow=max(0, max_overflow),
            pool_pre_ping=True,
            pool_recycle=max(30, pool_recycle),
            pool_timeout=max(1, pool_timeout),
            echo=sql_echo,
        )
        logger.info(
            "🐘 Configurando PostgreSQL database con pool de conexiones (size=%s, overflow=%s)",
            pool_size,
            max_overflow,
        )

    else:
        # Fallback genérico
        engine = create_engine(DATABASE_URL, echo=sql_echo)
        logger.info(f"🗄️ Configurando database genérica: {DATABASE_URL.split('://')[0]}")

    return engine


# Crear engine global
engine = create_database_engine()

# Crear session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_engine():
    """Obtener engine de base de datos"""
    return engine


def get_session():
    """Obtener sesión de base de datos (método legacy)"""
    return SessionLocal()


@contextmanager
def get_db_session() -> Generator:
    """
    Context manager para sesiones de base de datos
    Uso recomendado:

    with get_db_session() as db:
        # operaciones con db
        pass
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error en operación de base de datos: {e}")
        raise
    finally:
        session.close()


def initialize_schema() -> None:
    """Inicializar esquema de base de datos"""
    if not ALLOW_CREATE_ALL:
        logger.info("⏭️ initialize_schema omitido (DB_ALLOW_CREATE_ALL=false)")
        return

    try:
        logger.info("🚀 Inicializando esquema de base de datos...")
        Base.metadata.create_all(engine)
        logger.info("✅ Esquema de base de datos inicializado correctamente")
    except OperationalError as e:
        logger.error(f"❌ Error inicializando base de datos: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Error inesperado inicializando base de datos: {e}")
        raise


def test_connection() -> bool | None:
    """Probar conexión a la base de datos"""
    try:
        with get_db_session() as db:
            # Ejecutar query simple para probar conexión
            db.execute(text("SELECT 1"))
        logger.info("✅ Conexión a base de datos exitosa")
        return True
    except Exception as e:
        logger.error(f"❌ Error conectando a base de datos: {e}")
        return False


def get_db_info():
    """Obtener información de la base de datos"""
    try:
        db_type = DATABASE_URL.split("://")[0]

        return {
            "type": db_type,
            "url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,  # Ocultar credenciales
            "pool_size": getattr(engine.pool, "size", None),
            "checked_out": getattr(engine.pool, "checkedout", None),
            "overflow": getattr(engine.pool, "overflow", None),
            "checked_in": getattr(engine.pool, "checkedin", None),
            "connected": test_connection(),
        }

    except Exception as e:
        logger.error(f"Error obteniendo info de DB: {e}")
        return {"error": str(e)}


def cleanup_connections() -> None:
    """Limpiar conexiones de la pool"""
    try:
        engine.dispose()
        logger.info("🧹 Pool de conexiones limpiada")
    except Exception as e:
        logger.error(f"Error limpiando conexiones: {e}")


atexit.register(cleanup_connections)


# FastAPI dependency para inyección de dependencias
def get_db():
    """
    FastAPI dependency para obtener sesión de base de datos

    Uso en endpoints:
    async def endpoint(db: Session = Depends(get_db)):
        # usar db
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Función de migración simple
def migrate_sqlite_to_postgresql(postgresql_url: str) -> bool | None:
    """
    Migrar datos de SQLite a PostgreSQL (función básica)
    Para migraciones complejas, usar Alembic
    """
    if not DATABASE_URL.startswith("sqlite"):
        logger.error("Esta función solo funciona desde SQLite")
        return False

    pg_engine = None
    try:
        source_engine = engine

        # Crear engine de PostgreSQL
        pg_engine = create_engine(postgresql_url, pool_pre_ping=True)

        # Crear esquema en PostgreSQL (solo cuando está explícitamente permitido)
        if not ALLOW_CREATE_ALL:
            logger.error("Migración cancelada: DB_ALLOW_CREATE_ALL=false")
            return False
        Base.metadata.create_all(pg_engine)

        source_tables = set(inspect(source_engine).get_table_names())
        migrated_rows = 0

        with source_engine.connect() as source_conn, pg_engine.begin() as target_conn:
            for table in Base.metadata.sorted_tables:
                if table.name not in source_tables:
                    logger.info(f"ℹ️ Tabla {table.name} no existe en origen, omitiendo")
                    continue

                rows = source_conn.execute(table.select()).mappings().all()
                if not rows:
                    logger.info(f"ℹ️ Tabla {table.name} sin registros para migrar")
                    continue

                target_count = target_conn.execute(select(func.count()).select_from(table)).scalar_one()
                if target_count > 0:
                    logger.warning(
                        f"⚠️ Tabla destino {table.name} ya tiene {target_count} registros, se omite para evitar duplicados"
                    )
                    continue

                target_conn.execute(table.insert(), [dict(row) for row in rows])
                migrated_rows += len(rows)
                logger.info(f"✅ Migrados {len(rows)} registros en {table.name}")

        logger.info(f"✅ Migración completada. Total registros migrados: {migrated_rows}")
        return True

    except Exception as e:
        logger.error(f"Error en migración: {e}")
        return False
    finally:
        if pg_engine is not None:
            pg_engine.dispose()


# No crear/modificar esquema en import-time.


if __name__ == "__main__":
    # Script de prueba
    print("🧪 Probando conexión de base de datos...")
    print(f"Database URL: {DATABASE_URL}")

    if test_connection():
        print("✅ Conexión exitosa")
        print("ℹ️ Info de base de datos:")
        info = get_db_info()
        for key, value in info.items():
            print(f"  {key}: {value}")
    else:
        print("❌ Error de conexión")

    cleanup_connections()
