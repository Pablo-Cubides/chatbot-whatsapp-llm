"""
Modelos Pydantic para validación de datos
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class BusinessType(str, Enum):
    """Tipos de negocio soportados"""

    FLORISTERIA = "floristeria"
    PANADERIA = "panaderia"
    BUFETE_LEGAL = "bufete_legal"
    CLINICA = "clinica"
    TIENDA_ONLINE = "tienda_online"
    CONSULTORIA = "consultoria"
    EDUCACION = "educacion"
    HOTELERIA = "hoteleria"
    GENERAL = "general"


class ToneType(str, Enum):
    """Tonos de comunicación"""

    FORMAL = "formal"
    CASUAL_PROFESSIONAL = "casual_professional"
    CASUAL = "casual"
    AMIGABLE_PROFESIONAL = "amigable_profesional"


class ResponseLength(str, Enum):
    """Longitud de respuestas"""

    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class BusinessInfoModel(BaseModel):
    """Modelo para información del negocio"""

    name: str = Field(..., min_length=1, max_length=100, description="Nombre del negocio")
    description: str = Field(..., min_length=10, max_length=1000, description="Descripción del negocio")
    greeting: str = Field(..., min_length=10, max_length=500, description="Saludo inicial")
    closing: str = Field(..., min_length=10, max_length=500, description="Mensaje de despedida")
    tone: ToneType = Field(default=ToneType.CASUAL_PROFESSIONAL, description="Tono de comunicación")
    services: list[str] = Field(default_factory=list, max_items=20, description="Lista de servicios")
    hours: str = Field(..., max_length=200, description="Horario de atención")
    contact_info: str = Field(..., max_length=500, description="Información de contacto")
    website: Optional[str] = Field(None, max_length=200, description="Sitio web")
    location: Optional[str] = Field(None, max_length=200, description="Ubicación")

    @field_validator("services")
    @classmethod
    def validate_services(cls, v):
        if not v:
            raise ValueError("Debe incluir al menos un servicio")
        for service in v:
            if len(service.strip()) < 2:
                raise ValueError("Cada servicio debe tener al menos 2 caracteres")
        return v

    @field_validator("website")
    @classmethod
    def validate_website(cls, v):
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("La URL debe comenzar con http:// o https://")
        return v


class ClientObjectivesModel(BaseModel):
    """Modelo para objetivos con clientes"""

    primary_goal: str = Field(..., min_length=10, max_length=500, description="Objetivo principal")
    secondary_goals: list[str] = Field(default_factory=list, max_items=10, description="Objetivos secundarios")
    conversion_keywords: list[str] = Field(default_factory=list, max_items=50, description="Palabras clave de conversión")
    qualification_questions: list[str] = Field(default_factory=list, max_items=20, description="Preguntas de calificación")

    @field_validator("conversion_keywords")
    @classmethod
    def validate_keywords(cls, v):
        for keyword in v:
            if len(keyword.strip()) < 2:
                raise ValueError("Cada palabra clave debe tener al menos 2 caracteres")
        return v


class ConversationFlowModel(BaseModel):
    """Modelo para flujo de conversación"""

    greeting_variants: list[str] = Field(default_factory=list, max_items=10, description="Variantes de saludo")
    fallback_responses: list[str] = Field(default_factory=list, max_items=10, description="Respuestas de respaldo")
    escalation_triggers: list[str] = Field(default_factory=list, max_items=20, description="Triggers de escalación")

    @field_validator("greeting_variants")
    @classmethod
    def validate_greetings(cls, v):
        if not v:
            raise ValueError("Debe incluir al menos una variante de saludo")
        return v

    @field_validator("fallback_responses")
    @classmethod
    def validate_fallbacks(cls, v):
        if not v:
            raise ValueError("Debe incluir al menos una respuesta de respaldo")
        return v


class AIBehaviorModel(BaseModel):
    """Modelo para comportamiento de IA"""

    personality_traits: list[str] = Field(default_factory=list, max_items=15, description="Rasgos de personalidad")
    forbidden_topics: list[str] = Field(default_factory=list, max_items=30, description="Temas prohibidos")
    response_length: ResponseLength = Field(default=ResponseLength.MEDIUM, description="Longitud de respuestas")
    use_emojis: bool = Field(default=True, description="Usar emojis")
    formality_level: ToneType = Field(default=ToneType.CASUAL_PROFESSIONAL, description="Nivel de formalidad")


class WorkingScheduleModel(BaseModel):
    """Modelo para horario de trabajo de un día"""

    start: Optional[str] = Field(None, pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="Hora inicio (HH:MM)")
    end: Optional[str] = Field(None, pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="Hora fin (HH:MM)")
    closed: bool = Field(default=False, description="Día cerrado")

    @field_validator("end")
    @classmethod
    def validate_end_after_start(cls, v, info: ValidationInfo):
        start_time = info.data.get("start") if info and info.data else None
        if v and start_time:
            if v <= start_time:
                raise ValueError("La hora de fin debe ser posterior a la hora de inicio")
        return v


class WorkingHoursModel(BaseModel):
    """Modelo para horarios de trabajo"""

    enabled: bool = Field(default=True, description="Horarios habilitados")
    schedule: dict[str, WorkingScheduleModel] = Field(
        default_factory=lambda: {
            "monday": WorkingScheduleModel(start="09:00", end="18:00"),
            "tuesday": WorkingScheduleModel(start="09:00", end="18:00"),
            "wednesday": WorkingScheduleModel(start="09:00", end="18:00"),
            "thursday": WorkingScheduleModel(start="09:00", end="18:00"),
            "friday": WorkingScheduleModel(start="09:00", end="18:00"),
            "saturday": WorkingScheduleModel(closed=True),
            "sunday": WorkingScheduleModel(closed=True),
        },
        description="Horario por día de la semana",
    )
    outside_hours_message: str = Field(
        default="Gracias por contactarnos. Estamos fuera del horario de atención.",
        max_length=500,
        description="Mensaje fuera de horario",
    )

    @field_validator("schedule")
    @classmethod
    def validate_schedule_days(cls, v):
        required_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in required_days:
            if day not in v:
                raise ValueError(f"Falta configuración para {day}")
        return v


class BusinessRulesModel(BaseModel):
    """Modelo para reglas de negocio"""

    working_hours: WorkingHoursModel = Field(default_factory=WorkingHoursModel, description="Horarios de trabajo")
    auto_responses: bool = Field(default=True, description="Respuestas automáticas habilitadas")
    max_response_time: int = Field(default=5, ge=1, le=60, description="Tiempo máximo de respuesta (minutos)")
    escalation_after_attempts: int = Field(default=3, ge=1, le=10, description="Escalación después de X intentos")


class FullBusinessConfigModel(BaseModel):
    """Modelo completo de configuración de negocio"""

    business_info: BusinessInfoModel
    client_objectives: ClientObjectivesModel
    conversation_flow: ConversationFlowModel
    ai_behavior: AIBehaviorModel
    business_rules: BusinessRulesModel
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc), description="Fecha de creación")
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc), description="Fecha de actualización")

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})


class LLMRequestModel(BaseModel):
    """Modelo para solicitudes de LLM"""

    messages: list[dict[str, str]] = Field(..., min_length=1, description="Lista de mensajes")
    max_tokens: int = Field(default=150, ge=1, le=4000, description="Máximo tokens")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperatura")
    provider: Optional[str] = Field(None, description="Proveedor específico")
    free_only: bool = Field(default=False, description="Solo modelos gratuitos")
    use_case: str = Field(default="normal", pattern="^(normal|reasoning)$", description="Caso de uso")

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, v):
        for i, message in enumerate(v):
            if "role" not in message or "content" not in message:
                raise ValueError(f'Mensaje {i}: debe tener "role" y "content"')
            if message["role"] not in ["user", "assistant", "system"]:
                raise ValueError(f'Mensaje {i}: role debe ser "user", "assistant" o "system"')
            if len(message["content"].strip()) == 0:
                raise ValueError(f"Mensaje {i}: content no puede estar vacío")
        return v


class WhatsAppControlModel(BaseModel):
    """Modelo para control de WhatsApp"""

    action: str = Field(..., pattern="^(start|stop|restart)$", description="Acción a ejecutar")
    timeout: int = Field(default=60, ge=10, le=300, description="Timeout en segundos")


class AnalyticsFilterModel(BaseModel):
    """Modelo para filtros de analytics"""

    hours: int = Field(default=24, ge=1, le=8760, description="Horas a consultar")  # Max 1 año
    metric: Optional[str] = Field(None, pattern="^(conversations|messages|api_usage|errors)$", description="Métrica específica")
    start_date: Optional[datetime] = Field(None, description="Fecha inicio")
    end_date: Optional[datetime] = Field(None, description="Fecha fin")

    @field_validator("end_date")
    @classmethod
    def validate_end_after_start(cls, v, info: ValidationInfo):
        start_date = info.data.get("start_date") if info and info.data else None
        if v and start_date and v <= start_date:
            raise ValueError("end_date debe ser posterior a start_date")
        return v


class UserRegistrationModel(BaseModel):
    """Modelo para registro de usuarios"""

    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$", description="Nombre de usuario")
    password: str = Field(..., min_length=8, max_length=128, description="Contraseña")
    confirm_password: str = Field(..., description="Confirmación de contraseña")
    role: str = Field(default="operator", pattern="^(admin|operator)$", description="Rol del usuario")

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info: ValidationInfo):
        password = info.data.get("password") if info and info.data else None
        if password is not None and v != password:
            raise ValueError("Las contraseñas no coinciden")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("La contraseña debe contener al menos una mayúscula")
        if not any(c.islower() for c in v):
            raise ValueError("La contraseña debe contener al menos una minúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("La contraseña debe contener al menos un número")
        return v


class AuthLoginModel(BaseModel):
    """Modelo para login de autenticación"""

    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_.@-]+$", description="Usuario")
    password: str = Field(..., min_length=1, max_length=128, description="Contraseña")


class PasswordChangeModel(BaseModel):
    """Modelo para cambio de contraseña"""

    current_password: str = Field(..., description="Contraseña actual")
    new_password: str = Field(..., min_length=8, max_length=128, description="Nueva contraseña")
    confirm_new_password: str = Field(..., description="Confirmación de nueva contraseña")

    @field_validator("confirm_new_password")
    @classmethod
    def passwords_match(cls, v, info: ValidationInfo):
        new_password = info.data.get("new_password") if info and info.data else None
        if new_password is not None and v != new_password:
            raise ValueError("Las contraseñas nuevas no coinciden")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("La nueva contraseña debe contener al menos una mayúscula")
        if not any(c.islower() for c in v):
            raise ValueError("La nueva contraseña debe contener al menos una minúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("La nueva contraseña debe contener al menos un número")
        return v


class ErrorResponseModel(BaseModel):
    """Modelo para respuestas de error"""

    error: bool = True
    message: str
    details: Optional[dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})


class SuccessResponseModel(BaseModel):
    """Modelo para respuestas exitosas"""

    success: bool = True
    message: str
    data: Optional[dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})
