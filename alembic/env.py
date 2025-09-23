import sys
import os
from logging.config import fileConfig

# sqlalchemy imports removed as they are not needed in this simple env

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from admin_db import get_engine
from models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
from alembic import context

# Interpret the config file for Python logging.
config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

# Set the SQLAlchemy URL dynamically using the project's engine
def get_sqlalchemy_url():
    # We won't return a URL string; alembic can work with an Engine directly
    return None


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable too.
    """
    url = os.environ.get('DATABASE_URL')
    if not url:
        # Fallback to the engine's URL
        engine = get_engine()
        url = str(engine.url)

    context.configure(
        url=url,
        target_metadata=Base.metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we create an Engine and associate a connection with the context.
    """
    # Use project's engine for consistency
    engine = get_engine()

    connectable = engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
