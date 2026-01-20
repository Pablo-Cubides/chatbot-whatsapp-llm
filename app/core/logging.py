"""
📝 Configuración de Logging Estructurado
Logging en formato JSON para integración con sistemas de monitoreo.
"""

import logging
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """Formatter que produce logs en formato JSON."""
    
    def __init__(self, include_extras: bool = True):
        super().__init__()
        self.include_extras = include_extras
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Agregar exception info si existe
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Agregar extras si están disponibles
        if self.include_extras:
            extras = {
                k: v for k, v in record.__dict__.items()
                if k not in (
                    "name", "msg", "args", "created", "filename", "funcName",
                    "levelname", "levelno", "lineno", "module", "msecs",
                    "pathname", "process", "processName", "relativeCreated",
                    "stack_info", "exc_info", "exc_text", "message"
                )
            }
            if extras:
                log_data["extra"] = extras
        
        return json.dumps(log_data, default=str, ensure_ascii=False)


class ContextLogger:
    """Logger con contexto adicional para cada request."""
    
    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self._context: Dict[str, Any] = {}
    
    def set_context(self, **kwargs):
        """Establece contexto adicional para logs."""
        self._context.update(kwargs)
    
    def clear_context(self):
        """Limpia el contexto."""
        self._context.clear()
    
    def _log(self, level: int, msg: str, *args, **kwargs):
        extra = kwargs.pop("extra", {})
        extra.update(self._context)
        kwargs["extra"] = extra
        self._logger.log(level, msg, *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        self._log(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        self._log(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        self._log(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        self._log(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        self._log(logging.CRITICAL, msg, *args, **kwargs)


def setup_logging(
    level: Optional[str] = None,
    json_format: bool = True,
    log_file: Optional[str] = None
) -> None:
    """
    Configura el logging del sistema.
    
    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Si True, usa formato JSON para logs
        log_file: Archivo opcional para escribir logs
    """
    # Determinar nivel
    log_level = level or os.environ.get("LOG_LEVEL", "INFO")
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Limpiar handlers existentes
    root_logger.handlers.clear()
    
    # Formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (opcional)
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Reducir verbosidad de librerías externas
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    root_logger.info(
        "Logging configurado",
        extra={"level": log_level, "json_format": json_format, "log_file": log_file}
    )


def get_logger(name: str) -> ContextLogger:
    """
    Obtiene un logger con contexto.
    
    Args:
        name: Nombre del logger (normalmente __name__)
    
    Returns:
        ContextLogger con capacidad de agregar contexto
    """
    return ContextLogger(logging.getLogger(name))


# Configuración por defecto al importar
_configured = False

def ensure_logging_configured():
    """Asegura que el logging esté configurado."""
    global _configured
    if not _configured:
        json_format = os.environ.get("LOG_FORMAT", "json").lower() == "json"
        log_file = os.environ.get("LOG_FILE")
        setup_logging(json_format=json_format, log_file=log_file)
        _configured = True
