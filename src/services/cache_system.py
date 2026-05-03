"""
Sistema de caché con Redis para mejorar rendimiento
Caché de configuraciones, respuestas LLM y datos frecuentes
"""

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from cachetools import TTLCache

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = logging.getLogger(__name__)


class CacheManager:
    """Gestor de caché con soporte Redis y fallback en memoria"""

    def __init__(self) -> None:
        self.redis_client = None
        self.memory_cache = None  # type: ignore[assignment]
        self.cache_enabled = False
        self._key_locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

        # Configuración desde variables de entorno
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.cache_prefix = os.getenv("CACHE_PREFIX", "chatbot:")
        self.default_ttl = int(os.getenv("CACHE_DEFAULT_TTL", "3600"))  # 1 hora
        self.memory_cache = TTLCache(maxsize=10000, ttl=max(1, self.default_ttl))

        # Intentar conectar a Redis
        if REDIS_AVAILABLE:
            # Solo inicializar Redis si hay un event loop corriendo
            try:
                asyncio.get_running_loop()
                asyncio.create_task(self._initialize_redis())
            except RuntimeError:
                # No hay event loop, Redis se inicializará cuando se necesite
                logger.info("No hay event loop activo, Redis se inicializará bajo demanda")
        else:
            logger.warning("Redis no disponible, usando caché en memoria")

    async def _ensure_redis_initialized(self) -> None:
        """Asegurar que Redis esté inicializado"""
        if REDIS_AVAILABLE and self.redis_client is None and not hasattr(self, "_redis_init_attempted"):
            self._redis_init_attempted = True
            await self._initialize_redis()

    async def _initialize_redis(self) -> None:
        """Inicializar conexión Redis"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )

            # Probar conexión
            await self.redis_client.ping()
            self.cache_enabled = True
            logger.info("✅ Redis conectado exitosamente")

        except Exception as e:
            logger.warning(f"⚠️ No se pudo conectar a Redis: {e}. Usando caché en memoria")
            self.redis_client = None
            self.cache_enabled = False

    def _get_key(self, key: str) -> str:
        """Generar clave con prefijo"""
        return f"{self.cache_prefix}{key}"

    def _hash_key(self, data: Any) -> str:
        """Generar hash para claves complejas"""
        if isinstance(data, dict):
            # Serializar dict de forma determinística
            serialized = json.dumps(data, sort_keys=True)
        else:
            serialized = str(data)

        return hashlib.sha256(serialized.encode()).hexdigest()

    async def get(self, key: str) -> Any | None:
        """Obtener valor del caché"""
        try:
            await self._ensure_redis_initialized()
            cache_key = self._get_key(key)

            if self.redis_client and self.cache_enabled:
                # Obtener de Redis
                value = await self.redis_client.get(cache_key)
                if value:
                    return json.loads(value)
                return None
            # Obtener de memoria (TTLCache expira automáticamente)
            return self.memory_cache.get(cache_key)

        except Exception as e:
            logger.error(f"Error obteniendo caché {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Guardar valor en caché"""
        try:
            await self._ensure_redis_initialized()
            cache_key = self._get_key(key)
            ttl = ttl or self.default_ttl

            if self.redis_client and self.cache_enabled:
                # Guardar en Redis
                serialized_value = json.dumps(value, default=str)
                await self.redis_client.setex(cache_key, ttl, serialized_value)
                return True
            # Guardar en memoria (evicción automática LRU+TTL)
            self.memory_cache[cache_key] = value
            return True

        except Exception as e:
            logger.error(f"Error guardando caché {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Eliminar valor del caché"""
        try:
            cache_key = self._get_key(key)

            if self.redis_client and self.cache_enabled:
                await self.redis_client.delete(cache_key)
            else:
                if cache_key in self.memory_cache:
                    del self.memory_cache[cache_key]

            return True

        except Exception as e:
            logger.error(f"Error eliminando caché {key}: {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Limpiar claves que coincidan con patrón"""
        try:
            if self.redis_client and self.cache_enabled:
                # Redis scan para encontrar claves
                keys = []
                async for key in self.redis_client.scan_iter(match=self._get_key(pattern)):
                    keys.append(key)

                if keys:
                    await self.redis_client.delete(*keys)
                return len(keys)
            # Limpiar memoria
            pattern_key = self._get_key(pattern.replace("*", ""))
            keys_to_delete = [k for k in self.memory_cache if k.startswith(pattern_key)]
            for key in keys_to_delete:
                del self.memory_cache[key]
            return len(keys_to_delete)

        except Exception as e:
            logger.error(f"Error limpiando patrón {pattern}: {e}")
            return 0

    async def get_or_set(self, key: str, factory_func, ttl: int | None = None) -> Any:
        """Obtener del caché o calcular y guardar"""
        value = await self.get(key)
        if value is not None:
            return value

        async with self._locks_guard:
            lock = self._key_locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._key_locks[key] = lock

        async with lock:
            # Double-check después de adquirir el lock para evitar stampede
            value = await self.get(key)
            if value is not None:
                return value

            # Calcular valor
            if asyncio.iscoroutinefunction(factory_func):
                calculated_value = await factory_func()
            else:
                calculated_value = factory_func()

            # Guardar en caché
            await self.set(key, calculated_value, ttl)
            return calculated_value

    async def get_stats(self) -> dict[str, Any]:
        """Obtener estadísticas del caché"""
        stats = {
            "type": "redis" if self.cache_enabled and self.redis_client else "memory",
            "connected": self.cache_enabled,
            "prefix": self.cache_prefix,
            "default_ttl": self.default_ttl,
        }

        try:
            if self.redis_client and self.cache_enabled:
                info = await self.redis_client.info()
                stats.update(
                    {
                        "redis_version": info.get("redis_version"),
                        "used_memory": info.get("used_memory_human"),
                        "connected_clients": info.get("connected_clients"),
                        "keyspace_hits": info.get("keyspace_hits", 0),
                        "keyspace_misses": info.get("keyspace_misses", 0),
                    }
                )

                # Contar claves con nuestro prefijo
                key_count = 0
                async for _key in self.redis_client.scan_iter(match=f"{self.cache_prefix}*"):
                    key_count += 1
                stats["our_keys"] = key_count

            else:
                stats.update(
                    {
                        "memory_keys": len(self.memory_cache),
                        "memory_size_bytes": sum(len(str(v)) for v in self.memory_cache.values()),
                        "memory_cache_maxsize": getattr(self.memory_cache, "maxsize", 10000),
                    }
                )

        except Exception as e:
            stats["error"] = str(e)

        return stats

    async def health_check(self) -> bool:
        """Verificar salud del sistema de caché"""
        try:
            if self.redis_client and self.cache_enabled:
                await self.redis_client.ping()
                return True
            # Para memoria, siempre está "sano"
            return True
        except Exception as e:
            logger.error(f"Health check falló: {e}")
            return False

    def _cleanup_memory_cache(self) -> None:
        """Compatibility no-op: TTLCache handles expiration/eviction automatically."""
        return


# Instancia global del caché
cache_manager = CacheManager()


# Funciones de conveniencia para casos de uso específicos


async def cache_business_config(business_id: str, config: dict[str, Any], ttl: int = 7200) -> None:
    """Cachear configuración de negocio (2 horas por defecto)"""
    key = f"business_config:{business_id}"
    await cache_manager.set(key, config, ttl)


async def get_cached_business_config(business_id: str) -> dict[str, Any] | None:
    """Obtener configuración de negocio cacheada"""
    key = f"business_config:{business_id}"
    return await cache_manager.get(key)


async def cache_llm_response(prompt_hash: str, response: str, provider: str, ttl: int = 3600) -> None:
    """Cachear respuesta de LLM (1 hora por defecto)"""
    key = f"llm_response:{provider}:{prompt_hash}"
    cached_data = {"response": response, "provider": provider, "cached_at": datetime.now(timezone.utc).isoformat()}
    await cache_manager.set(key, cached_data, ttl)


async def get_cached_llm_response(prompt_hash: str, provider: str) -> dict[str, Any] | None:
    """Obtener respuesta de LLM cacheada"""
    key = f"llm_response:{provider}:{prompt_hash}"
    return await cache_manager.get(key)


async def cache_conversation_context(session_id: str, context: list[dict], ttl: int = 1800) -> None:
    """Cachear contexto de conversación (30 minutos por defecto)"""
    key = f"conversation:{session_id}"
    await cache_manager.set(key, context, ttl)


async def get_cached_conversation_context(session_id: str) -> list[dict] | None:
    """Obtener contexto de conversación cacheado"""
    key = f"conversation:{session_id}"
    return await cache_manager.get(key)


async def invalidate_business_cache(business_id: str) -> None:
    """Invalidar todo el caché relacionado con un negocio"""
    pattern = f"business_*:{business_id}"
    deleted = await cache_manager.clear_pattern(pattern)
    logger.info(f"Invalidadas {deleted} entradas de caché para negocio {business_id}")


async def clear_all_cache() -> None:
    """Limpiar todo el caché"""
    deleted = await cache_manager.clear_pattern("*")
    logger.info(f"Limpiadas {deleted} entradas del caché")


# Inicializar caché al importar
if __name__ != "__main__":
    # Solo inicializar si no estamos ejecutando como script principal
    pass


if __name__ == "__main__":
    # Script de prueba del caché
    async def test_cache() -> None:
        print("🧪 Probando sistema de caché...")

        # Probar set/get
        await cache_manager.set("test_key", {"message": "Hello Cache!"}, 60)
        result = await cache_manager.get("test_key")
        print(f"Test set/get: {result}")

        # Probar get_or_set
        def expensive_calculation():
            return {"calculated": "expensive value"}

        result = await cache_manager.get_or_set("calc_key", expensive_calculation, 120)
        print(f"Test get_or_set: {result}")

        # Mostrar estadísticas
        stats = await cache_manager.get_stats()
        print(f"Stats: {stats}")

        # Health check
        healthy = await cache_manager.health_check()
        print(f"Health: {'✅' if healthy else '❌'}")

    asyncio.run(test_cache())
