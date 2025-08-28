from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    Boolean,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    context = Column(Text, nullable=False)


class ModelConfig(Base):
    __tablename__ = "models"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    provider = Column(String, nullable=False)
    config = Column(JSON, nullable=True)
    active = Column(Boolean, default=True)


class Rule(Base):
    __tablename__ = "rules"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    every_n_messages = Column(Integer, nullable=False, default=0)
    model_id = Column(Integer, ForeignKey("models.id"))
    enabled = Column(Boolean, default=True)
    model = relationship("ModelConfig")


class AllowedContact(Base):
    __tablename__ = "allowed_contacts"
    id = Column(Integer, primary_key=True)
    contact_id = Column(String, unique=True, nullable=False)
    label = Column(String)
    owner_user = Column(String)
    added_at = Column(DateTime, default=datetime.utcnow)


class UserContext(Base):
    __tablename__ = "user_contexts"
    id = Column(Integer, primary_key=True)
    user_id = Column(String, index=True)
    text = Column(Text)
    source = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class DailyContext(Base):
    __tablename__ = "daily_contexts"
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.utcnow)
    text = Column(Text)
    created_by = Column(String)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    user_id = Column(String)
    action = Column(String)
    detail = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)


# ----------------------- New schema for two-agent pipeline -----------------------
class Contact(Base):
    __tablename__ = "contacts"
    # Use chat_id as primary key to align with WhatsApp chat title/number
    chat_id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    auto_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ChatProfile(Base):
    __tablename__ = "chat_profiles"
    chat_id = Column(String, primary_key=True)
    initial_context = Column(Text, default="")
    objective = Column(Text, default="")
    instructions = Column(Text, default="")
    is_ready = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ChatCounter(Base):
    __tablename__ = "chat_counters"
    chat_id = Column(String, primary_key=True)
    assistant_replies_count = Column(Integer, default=0)
    strategy_version = Column(Integer, default=0)
    last_reasoned_at = Column(DateTime, nullable=True)


class ChatStrategy(Base):
    __tablename__ = "chat_strategies"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, index=True, nullable=False)
    version = Column(Integer, default=1)
    strategy_text = Column(Text, nullable=False)
    source_snapshot = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
