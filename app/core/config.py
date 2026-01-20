"""
⚙️ Configuración Centralizada del Sistema
Todas las configuraciones se obtienen de variables de entorno con validación.
"""

import os
from typing import List, Optional
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class Settings:
    """Configuraciones del sistema centralizadas."""
    
    def __init__(self):
        # Server Configuration
        self.SERVER_HOST: str = os.environ.get("SERVER_HOST", "127.0.0.1")
        self.SERVER_PORT: int = int(os.environ.get("SERVER_PORT", "8003"))
        
        # Security
        self.JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
        self.JWT_EXPIRE_MINUTES: int = int(os.environ.get("JWT_EXPIRE_MINUTES", "1440"))
        self.LEGACY_TOKEN_ENABLED: bool = os.environ.get("LEGACY_TOKEN_ENABLED", "false").lower() == "true"
        
        # CORS
        _cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:8003,http://127.0.0.1:8003")
        self.CORS_ORIGINS: List[str] = [o.strip() for o in _cors_origins.split(",") if o.strip()]
        
        # Database
        self.DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///chatbot_context.db")
        
        # Redis
        self.REDIS_URL: Optional[str] = os.environ.get("REDIS_URL")
        
        # LM Studio
        self.LM_STUDIO_PORT: int = int(os.environ.get("LM_STUDIO_PORT", "1234"))
        self.LM_STUDIO_URL: str = os.environ.get("LM_STUDIO_URL", "http://127.0.0.1:1234/v1")
        
        # Logging
        self.LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
        
        # WhatsApp
        self.WHATSAPP_MODE: str = os.environ.get("WHATSAPP_MODE", "web")
        self.WHATSAPP_TIMEOUT: int = int(os.environ.get("WHATSAPP_TIMEOUT", "60"))
        
        # Audio Transcription
        self.AUDIO_TRANSCRIPTION_ENABLED: bool = os.environ.get("AUDIO_TRANSCRIPTION_ENABLED", "false").lower() == "true"
        self.WHISPER_MODEL_SIZE: str = os.environ.get("WHISPER_MODEL_SIZE", "base")
        
        # Alerting
        self.ALERTS_ENABLED: bool = os.environ.get("ALERTS_ENABLED", "true").lower() == "true"
        self.ALERT_WEBHOOK_URL: Optional[str] = os.environ.get("ALERT_WEBHOOK_URL")
        
        # Audit
        self.AUDIT_ENABLED: bool = os.environ.get("AUDIT_ENABLED", "true").lower() == "true"
    
    def validate(self) -> bool:
        """Valida configuración crítica."""
        errors = []
        
        if not self.JWT_SECRET:
            errors.append("JWT_SECRET no está configurado")
        elif len(self.JWT_SECRET) < 32:
            logger.warning("JWT_SECRET es muy corto (< 32 caracteres)")
        
        if errors:
            for error in errors:
                logger.error(f"Error de configuración: {error}")
            return False
        
        return True
    
    def get_database_url(self) -> str:
        """Retorna URL de base de datos apropiada."""
        return self.DATABASE_URL
    
    def is_development(self) -> bool:
        """Verifica si estamos en modo desarrollo."""
        return self.SERVER_HOST in ["127.0.0.1", "localhost"] or "DEBUG" in os.environ


@lru_cache()
def get_settings() -> Settings:
    """Obtiene instancia de settings (cached)."""
    settings = Settings()
    return settings


# Instancia global para acceso rápido
settings = get_settings()
