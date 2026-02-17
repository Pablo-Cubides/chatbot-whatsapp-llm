import pytest

from src.services.http_rate_limit import HttpRateLimiter


@pytest.mark.asyncio
async def test_http_rate_limiter_blocks_after_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_REDIS_ENABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_API_REQUESTS", "2")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")

    limiter = HttpRateLimiter()

    allowed_1, info_1 = await limiter.check_request(path="/api/models", identifier="127.0.0.1")
    allowed_2, info_2 = await limiter.check_request(path="/api/models", identifier="127.0.0.1")
    allowed_3, info_3 = await limiter.check_request(path="/api/models", identifier="127.0.0.1")

    assert allowed_1 is True
    assert allowed_2 is True
    assert allowed_3 is False
    assert info_1["limit"] == 2
    assert info_2["remaining"] == 0
    assert info_3["retry_after"] >= 0


@pytest.mark.asyncio
async def test_http_rate_limiter_has_endpoint_specific_rules(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_REDIS_ENABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_AUTH_REQUESTS", "1")
    monkeypatch.setenv("RATE_LIMIT_AUTH_WINDOW_SECONDS", "300")

    limiter = HttpRateLimiter()

    allowed_1, _ = await limiter.check_request(path="/api/auth/login", identifier="client-a")
    allowed_2, info_2 = await limiter.check_request(path="/api/auth/login", identifier="client-a")

    assert allowed_1 is True
    assert allowed_2 is False
    assert info_2["limit"] == 1
