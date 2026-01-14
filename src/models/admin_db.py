"""
Sistema de base de datos mejorado con soporte para PostgreSQL y SQLite
Pool de conexiones y configuración optimizada para producción
"""
import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import QueuePool, StaticPool
from typing import Generator

from models import Base

logger = logging.getLogger(__name__)

# Configuración de base de datos desde variables de entorno
DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite:///chatbot_context.db"


def create_database_engine():
    """Crear engine de base de datos con configuración optimizada"""
    
    if DATABASE_URL.startswith("sqlite"):
        # Configuración para SQLite
        engine = create_engine(
            DATABASE_URL,
            connect_args={
                "check_same_thread": False,
                "timeout": 20
            },
            poolclass=StaticPool,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true"
        )
        logger.info("🗃️ Configurando SQLite database")
        
    elif DATABASE_URL.startswith("postgresql"):
        # Configuración para PostgreSQL
        engine = create_engine(
            DATABASE_URL,
            poolclass=QueuePool,
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true"
        )
        logger.info("🐘 Configurando PostgreSQL database con pool de conexiones")
        
    else:
        # Fallback genérico
        engine = create_engine(
            DATABASE_URL,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true"
        )
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


def initialize_schema():
    """Inicializar esquema de base de datos"""
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


def test_connection():
    """Probar conexión a la base de datos"""
    try:
        with get_db_session() as db:
            # Ejecutar query simple para probar conexión
            if DATABASE_URL.startswith("postgresql"):
                db.execute("SELECT 1")
            else:
                db.execute("SELECT 1")
        logger.info("✅ Conexión a base de datos exitosa")
        return True
    except Exception as e:
        logger.error(f"❌ Error conectando a base de datos: {e}")
        return False


def get_db_info():
    """Obtener información de la base de datos"""
    try:
        db_type = DATABASE_URL.split("://")[0]
        
        info = {
            "type": db_type,
            "url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,  # Ocultar credenciales
            "pool_size": getattr(engine.pool, 'size', None),
            "checked_out": getattr(engine.pool, 'checkedout', None),
            "overflow": getattr(engine.pool, 'overflow', None),
            "checked_in": getattr(engine.pool, 'checkedin', None),
            "connected": test_connection()
        }
        
        return info
    except Exception as e:
        logger.error(f"Error obteniendo info de DB: {e}")
        return {"error": str(e)}


def cleanup_connections():
    """Limpiar conexiones de la pool"""
    try:
        engine.dispose()
        logger.info("🧹 Pool de conexiones limpiada")
    except Exception as e:
        logger.error(f"Error limpiando conexiones: {e}")


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
    finally:
        db.close()


# Función de migración simple
def migrate_sqlite_to_postgresql(postgresql_url: str):
    """
    Migrar datos de SQLite a PostgreSQL (función básica)
    Para migraciones complejas, usar Alembic
    """
    if not DATABASE_URL.startswith("sqlite"):
        logger.error("Esta función solo funciona desde SQLite")
        return False
    
    try:
        # Crear engine de PostgreSQL
        pg_engine = create_engine(postgresql_url)
        
        # Crear esquema en PostgreSQL
        Base.metadata.create_all(pg_engine)
        
        # TODO: Implementar migración de datos
        # Esta es una implementación básica, para casos reales usar Alembic
        
        logger.info("⚠️ Migración básica completada. Revisar datos manualmente.")
        return True
        
    except Exception as e:
        logger.error(f"Error en migración: {e}")
        return False


# Inicializar base de datos al importar el módulo
if __name__ != "__main__":
    try:
        initialize_schema()
    except Exception as e:
        logger.warning(f"No se pudo inicializar la base de datos automáticamente: {e}")


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
