"""HTTP rate limiting with Redis backend and in-memory fallback."""

import asyncio
import ipaddress
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

REDIS_BACKEND: Any = None

try:
    import redis.asyncio as redis_asyncio

    REDIS_BACKEND = redis_asyncio
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitConfig:
    requests: int
    window_seconds: int


class HttpRateLimiter:
    """Rate limiter for FastAPI middleware-level throttling."""

    def __init__(self) -> None:
        self.enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        self.redis_enabled = os.getenv("RATE_LIMIT_REDIS_ENABLED", "true").lower() == "true"
        self.redis_url = os.getenv("RATE_LIMIT_REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        self.prefix = os.getenv("RATE_LIMIT_PREFIX", "ratelimit:http")

        default_window = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
        default_requests = int(os.getenv("RATE_LIMIT_API_REQUESTS", "120"))

        self.api_general = RateLimitConfig(requests=default_requests, window_seconds=default_window)
        self.auth_login = RateLimitConfig(
            requests=int(os.getenv("RATE_LIMIT_AUTH_REQUESTS", "10")),
            window_seconds=int(os.getenv("RATE_LIMIT_AUTH_WINDOW_SECONDS", "300")),
        )
        self.system_control = RateLimitConfig(
            requests=int(os.getenv("RATE_LIMIT_SYSTEM_REQUESTS", "30")),
            window_seconds=int(os.getenv("RATE_LIMIT_SYSTEM_WINDOW_SECONDS", "60")),
        )

        self._memory_store: dict[str, tuple[int, float]] = {}
        self._memory_lock = asyncio.Lock()
        self._redis_client: Any | None = None
        self._redis_init_attempted = False

    async def _ensure_redis(self) -> None:
        if not self.redis_enabled or not REDIS_AVAILABLE:
            return
        if self._redis_client is not None or self._redis_init_attempted:
            return

        self._redis_init_attempted = True
        try:
            self._redis_client = REDIS_BACKEND.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
            )
            await self._redis_client.ping()
            logger.info("✅ HTTP rate limiter using Redis backend")
        except Exception as e:
            self._redis_client = None
            logger.warning("⚠️ HTTP rate limiter fallback to memory: %s", e)

    @staticmethod
    def get_client_identifier(request: Any) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            candidate = forwarded.split(",")[0].strip()
            try:
                ipaddress.ip_address(candidate)
                return str(candidate)
            except ValueError:
                logger.warning("⚠️ Invalid X-Forwarded-For IP ignored: %s", candidate)

        client_host = request.client.host if request.client else "unknown"
        try:
            ipaddress.ip_address(client_host)
            return client_host
        except ValueError:
            return "unknown"

    def _rule_for_path(self, path: str) -> tuple[str, RateLimitConfig]:
        if path.startswith("/api/auth/login"):
            return "auth_login", self.auth_login
        if path.startswith("/api/system/"):
            return "system_control", self.system_control
        return "api_general", self.api_general

    async def check_request(self, path: str, identifier: str) -> tuple[bool, dict[str, int]]:
        if not self.enabled:
            return True, {"limit": 0, "remaining": 0, "reset": 0, "retry_after": 0}

        bucket_name, rule = self._rule_for_path(path)
        await self._ensure_redis()

        now = int(time.time())
        window = max(1, rule.window_seconds)
        window_bucket = now // window
        reset_at = (window_bucket + 1) * window
        ttl = max(1, reset_at - now)
        key = f"{self.prefix}:{bucket_name}:{identifier}:{window_bucket}"

        current = None

        if self._redis_client is not None:
            try:
                current = int(await self._redis_client.incr(key))
                if current == 1:
                    await self._redis_client.expire(key, ttl)
            except Exception as e:
                logger.warning("⚠️ HTTP rate limiter Redis error, using memory: %s", e)
                self._redis_client = None

        if current is None:
            async with self._memory_lock:
                count, expires_at = self._memory_store.get(key, (0, float(reset_at)))
                if expires_at <= now:
                    count = 0
                    expires_at = float(reset_at)
                count += 1
                self._memory_store[key] = (count, expires_at)
                current = count

                stale_keys = [k for k, (_, exp) in self._memory_store.items() if exp <= now]
                for stale_key in stale_keys:
                    self._memory_store.pop(stale_key, None)

        allowed = current <= rule.requests
        remaining = max(0, rule.requests - current)
        info = {
            "limit": rule.requests,
            "remaining": remaining,
            "reset": reset_at,
            "retry_after": max(0, reset_at - now),
        }
        return allowed, info

    async def aclose(self) -> None:
        """Close backend clients and clear transient in-memory state."""
        try:
            if self._redis_client is not None:
                await self._redis_client.close()
        except Exception as e:
            logger.warning("⚠️ Error closing HTTP rate limiter Redis client: %s", e)
        finally:
            self._redis_client = None
            self._redis_init_attempted = False
            self._memory_store.clear()


http_rate_limiter = HttpRateLimiter()
