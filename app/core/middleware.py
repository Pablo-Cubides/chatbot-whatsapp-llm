"""
🚀 Middleware de Métricas y Logging
Middleware para capturar métricas de requests y logging automático.
"""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware para capturar métricas de cada request."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.request_count = 0
        self.error_count = 0
        self.total_duration = 0.0
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Incrementar contador de requests
        self.request_count += 1
        
        # Procesar request
        try:
            response = await call_next(request)
            
            # Calcular duración
            duration = time.time() - start_time
            self.total_duration += duration
            
            # Log de request completado
            logger.debug(
                f"{request.method} {request.url.path} - {response.status_code}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "client_ip": request.client.host if request.client else None
                }
            )
            
            # Contar errores
            if response.status_code >= 400:
                self.error_count += 1
            
            # Agregar headers de métricas
            response.headers["X-Response-Time"] = f"{duration * 1000:.2f}ms"
            
            return response
            
        except Exception as e:
            self.error_count += 1
            duration = time.time() - start_time
            
            logger.error(
                f"Error procesando {request.method} {request.url.path}: {e}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration * 1000, 2),
                    "error": str(e)
                }
            )
            raise
    
    def get_stats(self) -> dict:
        """Retorna estadísticas del middleware."""
        avg_duration = (
            self.total_duration / self.request_count 
            if self.request_count > 0 else 0
        )
        return {
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "error_rate": self.error_count / self.request_count if self.request_count > 0 else 0,
            "avg_response_time_ms": round(avg_duration * 1000, 2)
        }


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware para agregar headers de seguridad."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Headers de seguridad
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # HSTS solo en producción (cuando hay HTTPS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware para agregar ID único a cada request."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        import uuid
        
        # Generar o usar request ID existente
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
        
        # Guardar en state para uso en la aplicación
        request.state.request_id = request_id
        
        response = await call_next(request)
        
        # Agregar a response
        response.headers["X-Request-ID"] = request_id
        
        return response


def setup_middlewares(app):
    """Configura todos los middlewares en la aplicación FastAPI."""
    
    # Orden importante: primero los que wrappean, después los que modifican
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MetricsMiddleware)
    
    logger.info("Middlewares de seguridad y métricas configurados")
