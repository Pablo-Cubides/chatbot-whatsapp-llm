import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

from models import Base


DB_URL = os.environ.get("DATABASE_URL") or f"sqlite:///chatbot_context.db"


def get_engine():
    engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
    return engine


def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def initialize_schema():
    engine = get_engine()
    try:
        Base.metadata.create_all(engine)
    except OperationalError:
        # In some environments the sqlite file may be locked; propagate
        raise
