from fastapi.testclient import TestClient

from src.services.http_rate_limit import RateLimitConfig, http_rate_limiter


def test_api_rate_limit_blocks_after_threshold(client: TestClient) -> None:
    http_rate_limiter.enabled = True
    http_rate_limiter.redis_enabled = False
    http_rate_limiter.api_general = RateLimitConfig(requests=1, window_seconds=60)
    http_rate_limiter.auth_login = RateLimitConfig(requests=1, window_seconds=60)
    http_rate_limiter._memory_store.clear()

    payload = {"username": "admin", "password": "invalid-password"}
    first = client.post("/api/auth/login", json=payload)
    second = client.post("/api/auth/login", json=payload)

    assert first.status_code == 401
    assert second.status_code == 429
    assert "X-RateLimit-Limit" in second.headers
    assert "X-RateLimit-Remaining" in second.headers
    assert second.json().get("detail") == "Rate limit exceeded"
