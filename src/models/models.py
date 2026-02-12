from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

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
    model_type = Column(String, default="local")  # 'local' or 'online'
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


# ----------------------- Humanization & Transfer Models -----------------------
class SilentTransfer(Base):
    """Transferencias silenciosas a humanos"""

    __tablename__ = "silent_transfers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transfer_id = Column(String(100), unique=True, nullable=False, index=True)
    chat_id = Column(String(200), nullable=False, index=True)

    # Razón y contexto
    reason = Column(String(50), nullable=False, index=True)
    trigger_message = Column(Text, nullable=True)
    conversation_context = Column(JSON, nullable=True)

    # Estado
    status = Column(String(20), default="pending", nullable=False, index=True)
    priority = Column(Integer, default=5, nullable=False)

    # Tiempos
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    assigned_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Asignación
    assigned_to = Column(String(100), nullable=True, index=True)

    # Transfer metadata
    transfer_metadata = Column("metadata", JSON, nullable=True)
    notes = Column(Text, nullable=True)
    client_notified = Column(Boolean, default=False, nullable=False)


class HumanizationMetric(Base):
    """Métricas de humanización del bot"""

    __tablename__ = "humanization_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(200), index=True, nullable=False)
    session_id = Column(String(100), index=True)

    # Métricas críticas
    bot_suspicion_detected = Column(Boolean, default=False, nullable=False)
    bot_suspicion_triggers = Column(JSON, nullable=True)
    bot_suspicion_level = Column(Integer, default=0)  # 0-10

    # Contadores
    silent_transfers_count = Column(Integer, default=0)
    humanized_responses_count = Column(Integer, default=0)
    simple_question_failures = Column(Integer, default=0)
    ethical_refusals = Column(Integer, default=0)

    # Validación de respuestas
    bot_revealing_responses = Column(Integer, default=0)
    responses_humanized = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConversationObjective(Base):
    """Objetivos y resultados de conversaciones"""

    __tablename__ = "conversation_objectives"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(200), index=True, nullable=False)
    session_id = Column(String(100), index=True)

    # Objetivos
    global_objective = Column(String(100))  # venta, cita, soporte, lead
    client_objective = Column(Text)  # objetivo específico del cliente

    # Resultado
    objective_achieved = Column(String(20))  # yes, no, partial
    conversion_happened = Column(Boolean, default=False)

    # Emociones
    initial_emotion = Column(String(50))
    final_emotion = Column(String(50))
    emotion_trend = Column(String(20))  # improving, stable, declining

    # Calidad
    satisfaction_score = Column(Integer)  # 0-10
    response_quality_score = Column(Integer)  # 0-10

    # Análisis
    failure_reasons = Column(JSON, nullable=True)
    success_factors = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


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


# ----------------------- Appointment Scheduling Models -----------------------
class Appointment(Base):
    """Citas agendadas a través del chatbot"""

    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    appointment_id = Column(String(100), unique=True, nullable=False, index=True)
    chat_id = Column(String(200), nullable=False, index=True)

    # Información de la cita
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    timezone = Column(String(50), default="America/Bogota")
    location = Column(String(500), nullable=True)  # Puede ser URL de meet/teams o dirección física

    # Información del cliente
    client_name = Column(String(200), nullable=False)
    client_email = Column(String(200), nullable=True)
    client_phone = Column(String(50), nullable=True)

    # Proveedor de calendario y estado
    provider = Column(String(50), nullable=False, index=True)  # google_calendar, outlook
    status = Column(String(30), default="pending", nullable=False, index=True)
    # Estados: pending, confirmed, cancelled, completed, no_show, rescheduled

    # IDs y links externos
    external_id = Column(String(300), nullable=True)  # ID en Google/Outlook
    external_link = Column(String(500), nullable=True)  # Link para unirse a la reunión
    ical_uid = Column(String(300), nullable=True)  # UID del evento iCal

    # Metadatos
    reminder_sent = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    extra_metadata = Column("metadata", JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    cancelled_at = Column(DateTime, nullable=True)


class CalendarCredential(Base):
    """Credenciales OAuth para servicios de calendario"""

    __tablename__ = "calendar_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False, unique=True, index=True)  # google_calendar, outlook

    # Tokens OAuth (encriptados en producción)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_type = Column(String(50), default="Bearer")

    # Información de expiración
    expires_at = Column(DateTime, nullable=True)
    scope = Column(Text, nullable=True)

    # Información de la cuenta
    account_email = Column(String(200), nullable=True)
    calendar_id = Column(String(300), nullable=True)  # ID del calendario a usar

    # Estado
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
