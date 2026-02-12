"""
Sistema de Rate Limiting y Circuit Breaker para proteger APIs
"""

import asyncio
import functools
import ipaddress
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Estados del Circuit Breaker"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerStats:
    """Estadísticas del Circuit Breaker"""

    failure_count: int = 0
    success_count: int = 0
    total_requests: int = 0
    last_failure_time: Optional[datetime] = None
    state_changed_at: datetime = field(default_factory=datetime.utcnow)


class CircuitBreaker:
    """
    Circuit Breaker para proteger llamadas a APIs externas
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: tuple = (Exception,),
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        self.state = CircuitBreakerState.CLOSED
        self.stats = CircuitBreakerStats()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Ejecutar función con protección Circuit Breaker"""

        self.stats.total_requests += 1

        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self.stats.state_changed_at = datetime.now(timezone.utc)
                logger.info(f"Circuit breaker {self.name}: OPEN -> HALF_OPEN")
            else:
                raise CircuitBreakerOpenException(f"Circuit breaker {self.name} is OPEN")

        try:
            # Ejecutar función
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Éxito
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Verificar si debemos intentar reset después del timeout"""
        if self.stats.last_failure_time is None:
            return True

        time_since_last_failure = datetime.now(timezone.utc) - self.stats.last_failure_time
        return time_since_last_failure.total_seconds() >= self.recovery_timeout

    def _on_success(self):
        """Manejar caso de éxito"""
        self.stats.success_count += 1
        self.stats.failure_count = 0  # Reset failure count

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            self.stats.state_changed_at = datetime.now(timezone.utc)
            logger.info(f"Circuit breaker {self.name}: HALF_OPEN -> CLOSED")

    def _on_failure(self):
        """Manejar caso de fallo"""
        self.stats.failure_count += 1
        self.stats.last_failure_time = datetime.now(timezone.utc)

        if self.stats.failure_count >= self.failure_threshold and self.state == CircuitBreakerState.CLOSED:
            self.state = CircuitBreakerState.OPEN
            self.stats.state_changed_at = datetime.now(timezone.utc)
            logger.warning(f"Circuit breaker {self.name}: CLOSED -> OPEN")

        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            self.stats.state_changed_at = datetime.now(timezone.utc)
            logger.warning(f"Circuit breaker {self.name}: HALF_OPEN -> OPEN")

    def get_stats(self) -> dict[str, Any]:
        """Obtener estadísticas del circuit breaker"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.stats.failure_count,
            "success_count": self.stats.success_count,
            "total_requests": self.stats.total_requests,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self.stats.last_failure_time.isoformat() if self.stats.last_failure_time else None,
            "state_changed_at": self.stats.state_changed_at.isoformat(),
        }


class CircuitBreakerOpenException(Exception):
    """Excepción cuando el circuit breaker está abierto"""

    pass


@dataclass
class RateLimitRule:
    """Regla de rate limiting"""

    requests: int  # Número de requests
    window: int  # Ventana de tiempo en segundos
    identifier: str = "global"  # Identificador para rate limit específico


class RateLimiter:
    """
    Rate Limiter usando algoritmo de sliding window
    """

    def __init__(self):
        self.request_history: dict[str, list] = {}

    def is_allowed(self, rule: RateLimitRule, identifier: str = None) -> tuple[bool, dict[str, Any]]:
        """
        Verificar si request está permitido

        Returns:
            (allowed: bool, info: dict)
        """
        key = identifier or rule.identifier
        current_time = time.time()

        # Inicializar historial si no existe
        if key not in self.request_history:
            self.request_history[key] = []

        history = self.request_history[key]

        # Limpiar requests antiguos fuera de la ventana
        cutoff_time = current_time - rule.window
        history[:] = [req_time for req_time in history if req_time > cutoff_time]

        # Verificar límite
        current_requests = len(history)
        allowed = current_requests < rule.requests

        if allowed:
            history.append(current_time)

        info = {
            "requests_made": current_requests,
            "requests_limit": rule.requests,
            "window_seconds": rule.window,
            "reset_time": cutoff_time + rule.window,
            "remaining_requests": max(0, rule.requests - current_requests - (1 if allowed else 0)),
        }

        return allowed, info

    def cleanup_stale_entries(self, max_age: int = 600):
        """Remove stale entries older than max_age seconds to prevent memory leak"""
        current_time = time.time()
        cutoff = current_time - max_age
        stale_keys = [key for key, history in self.request_history.items() if not history or all(t < cutoff for t in history)]
        for key in stale_keys:
            del self.request_history[key]
        if stale_keys:
            logger.debug(f"🧹 Limpiados {len(stale_keys)} identifiers stale del rate limiter")

    def get_stats(self) -> dict[str, Any]:
        """Obtener estadísticas del rate limiter"""
        # Periodic cleanup on stats call
        self.cleanup_stale_entries()

        current_time = time.time()
        stats = {
            "active_identifiers": len(self.request_history),
            "total_tracked_requests": sum(len(history) for history in self.request_history.values()),
            "identifiers": {},
        }

        for identifier, history in self.request_history.items():
            # Contar requests recientes (últimos 5 minutos)
            recent_requests = sum(1 for req_time in history if current_time - req_time < 300)
            stats["identifiers"][identifier] = {"total_requests": len(history), "recent_requests_5min": recent_requests}

        return stats


# Instancias globales
circuit_breakers: dict[str, CircuitBreaker] = {}
rate_limiter = RateLimiter()

# Rate limiting rules predefinidas
RATE_LIMIT_RULES = {
    "api_general": RateLimitRule(requests=100, window=60, identifier="api_general"),
    "llm_requests": RateLimitRule(requests=20, window=60, identifier="llm_requests"),
    "whatsapp_messages": RateLimitRule(requests=30, window=60, identifier="whatsapp_messages"),
    "auth_attempts": RateLimitRule(requests=5, window=300, identifier="auth_attempts"),  # 5 per 5 minutes
}


def get_or_create_circuit_breaker(name: str, failure_threshold: int = 5, recovery_timeout: int = 60) -> CircuitBreaker:
    """Obtener o crear circuit breaker"""
    if name not in circuit_breakers:
        circuit_breakers[name] = CircuitBreaker(
            failure_threshold=failure_threshold, recovery_timeout=recovery_timeout, name=name
        )
    return circuit_breakers[name]


def circuit_breaker(name: str, failure_threshold: int = 5, recovery_timeout: int = 60):
    """Decorator para proteger funciones con circuit breaker"""

    def decorator(func):
        cb = get_or_create_circuit_breaker(name, failure_threshold, recovery_timeout)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await cb.call(func, *args, **kwargs)

        return wrapper

    return decorator


def rate_limit(rule_name: str, identifier_func: Optional[Callable] = None):
    """Decorator para aplicar rate limiting"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            rule = RATE_LIMIT_RULES.get(rule_name)
            if not rule:
                logger.warning(f"Rate limit rule '{rule_name}' no encontrada")
                return await func(*args, **kwargs)

            # Determinar identificador
            identifier = rule.identifier
            if identifier_func:
                try:
                    identifier = identifier_func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Error obteniendo identificador para rate limit: {e}")

            # Verificar rate limit
            allowed, info = rate_limiter.is_allowed(rule, identifier)

            if not allowed:
                from fastapi import HTTPException

                raise HTTPException(status_code=429, detail={"error": "Rate limit exceeded", "rule": rule_name, "info": info})

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# Funciones de utilidad para FastAPI


def get_client_ip(request) -> str:
    """Obtener IP del cliente para rate limiting (con validación)"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        candidate = forwarded.split(",")[0].strip()
        # Validate that it looks like a real IP address
        try:
            ipaddress.ip_address(candidate)
            return candidate
        except ValueError:
            logger.warning(f"⚠️ X-Forwarded-For con IP inválida: {candidate}")
            pass
    return request.client.host


def get_user_identifier(request) -> str:
    """Obtener identificador de usuario para rate limiting"""
    # Intentar obtener de token JWT
    auth_header = request.headers.get("Authorization")
    if auth_header:
        try:
            import hashlib

            token_hash = hashlib.sha256(auth_header.encode()).hexdigest()[:12]
            return f"user_{token_hash}"
        except Exception:
            pass

    # Fallback a IP
    return f"ip_{get_client_ip(request)}"


# Middleware FastAPI para rate limiting automático
class RateLimitMiddleware:
    """Middleware para aplicar rate limiting automático"""

    def __init__(self, app, default_rule: str = "api_general"):
        self.app = app
        self.default_rule = default_rule

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Crear request object simplificado
        dict(scope.get("headers", []))
        client_ip = scope.get("client", ["unknown", None])[0]

        # Aplicar rate limiting
        rule = RATE_LIMIT_RULES.get(self.default_rule)
        if rule:
            identifier = f"ip_{client_ip}"
            allowed, info = rate_limiter.is_allowed(rule, identifier)

            if not allowed:
                # Respuesta 429 Too Many Requests
                response = {"error": "Rate limit exceeded", "info": info}

                await send(
                    {
                        "type": "http.response.start",
                        "status": 429,
                        "headers": [
                            [b"content-type", b"application/json"],
                            [b"x-ratelimit-limit", str(rule.requests).encode()],
                            [b"x-ratelimit-remaining", str(info["remaining_requests"]).encode()],
                            [b"x-ratelimit-reset", str(int(info["reset_time"])).encode()],
                        ],
                    }
                )

                import json

                await send({"type": "http.response.body", "body": json.dumps(response).encode()})
                return

        # Continuar con la aplicación
        await self.app(scope, receive, send)


def get_protection_stats() -> dict[str, Any]:
    """Obtener estadísticas de todos los sistemas de protección"""
    stats = {
        "rate_limiter": rate_limiter.get_stats(),
        "circuit_breakers": {name: cb.get_stats() for name, cb in circuit_breakers.items()},
        "protection_rules": {
            name: {"requests": rule.requests, "window": rule.window, "identifier": rule.identifier}
            for name, rule in RATE_LIMIT_RULES.items()
        },
    }

    return stats


if __name__ == "__main__":
    # Tests de desarrollo - no importar en producción
    async def _test_circuit_breaker():
        @circuit_breaker("test_cb", failure_threshold=2, recovery_timeout=5)
        async def failing_function(should_fail: bool = True):
            if should_fail:
                raise Exception("Simulated failure")
            return "Success!"

        print("🧪 Probando Circuit Breaker...")
        try:
            result = await failing_function(False)
            print(f"✅ Éxito: {result}")
        except Exception as e:
            print(f"❌ Error: {e}")

        for i in range(3):
            try:
                await failing_function(True)
            except Exception as e:
                print(f"❌ Falla {i + 1}: {type(e).__name__}")

        try:
            await failing_function(False)
        except CircuitBreakerOpenException as e:
            print(f"🚫 Circuit Breaker OPEN: {e}")

        cb = circuit_breakers["test_cb"]
        print(f"📊 Stats: {cb.get_stats()}")

    asyncio.run(_test_circuit_breaker())
