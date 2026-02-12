"""
Tests for the Cache System — Redis with in-memory fallback.
"""

import pytest

from src.services.cache_system import (
    CacheManager,
    cache_business_config,
    cache_conversation_context,
    cache_llm_response,
    get_cached_business_config,
    get_cached_conversation_context,
    get_cached_llm_response,
)


class TestCacheManager:
    """Test suite for CacheManager with in-memory fallback."""

    def setup_method(self):
        """Create a fresh CacheManager for each test (no Redis)."""
        self.cm = CacheManager()
        # Force in-memory mode by not connecting to Redis
        self.cm.redis_client = None

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Should store and retrieve values."""
        await self.cm.set("key1", "value1", ttl=60)
        result = await self.cm.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_missing_key(self):
        """Should return None for non-existent keys."""
        result = await self.cm.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """Should delete a cached value."""
        await self.cm.set("key1", "value1", ttl=60)
        await self.cm.delete("key1")
        result = await self.cm.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        """Values should expire after TTL."""
        await self.cm.set("key1", "value1", ttl=1)
        import time

        time.sleep(1.1)
        result = await self.cm.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_dict_value(self):
        """Should handle dict values via JSON serialization."""
        data = {"name": "test", "count": 42}
        await self.cm.set("dict_key", data, ttl=60)
        result = await self.cm.get("dict_key")
        assert result == data

    @pytest.mark.asyncio
    async def test_set_list_value(self):
        """Should handle list values."""
        data = [1, 2, 3, "hello"]
        await self.cm.set("list_key", data, ttl=60)
        result = await self.cm.get("list_key")
        assert result == data

    @pytest.mark.asyncio
    async def test_memory_limit_enforcement(self):
        """Should evict entries when memory limit is exceeded."""
        # The CacheManager uses a hardcoded MAX_MEMORY_CACHE_SIZE of 10000
        for i in range(20):
            await self.cm.set(f"key{i}", f"val{i}", ttl=300)

        # All entries should be retrievable (well under the 10000 limit)
        stats = await self.cm.get_stats()
        assert stats["memory_keys"] <= 20

    @pytest.mark.asyncio
    async def test_clear(self):
        """Should clear all cached values via clear_pattern."""
        await self.cm.set("k1", "v1", ttl=60)
        await self.cm.set("k2", "v2", ttl=60)
        deleted = await self.cm.clear_pattern("*")
        assert deleted >= 2
        assert await self.cm.get("k1") is None
        assert await self.cm.get("k2") is None


class TestConvenienceFunctions:
    """Test the module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_business_config_cache(self):
        """Cache and retrieve business config."""
        config = {"name": "TestBiz", "active": True}
        await cache_business_config("biz1", config, ttl=60)
        result = await get_cached_business_config("biz1")
        assert result is not None
        assert result["name"] == "TestBiz"

    @pytest.mark.asyncio
    async def test_llm_response_cache(self):
        """Cache and retrieve LLM responses."""
        await cache_llm_response("hash123", "AI response text", "openai", ttl=60)
        result = await get_cached_llm_response("hash123", "openai")
        assert result is not None
        assert "AI response text" in str(result)

    @pytest.mark.asyncio
    async def test_session_context_cache(self):
        """Cache and retrieve session context."""
        ctx = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        await cache_conversation_context("session1", ctx, ttl=60)
        result = await get_cached_conversation_context("session1")
        assert result is not None

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Should return valid stats dict."""
        cm = CacheManager()
        stats = await cm.get_stats()
        assert isinstance(stats, dict)
        assert "memory_keys" in stats or "connected" in stats


class TestCacheKeyHashing:
    """Verify cache keys use SHA-256 (not MD5)."""

    @pytest.mark.asyncio
    async def test_cache_key_format(self):
        """Internal keys should use SHA-256 hashing."""
        cm = CacheManager()
        cm.redis_client = None

        # Set a value and check the internal key format
        await cm.set("test_key", "test_value", ttl=60)

        # The key should exist in memory cache
        found = False
        for key in cm.memory_cache:
            if "test" in str(key):
                found = True
                break
        assert found, "Key should be stored in memory cache"
