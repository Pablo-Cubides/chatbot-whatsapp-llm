"""
Tests for the Protection System — Rate Limiting & Circuit Breaker.
"""

import time

from src.services.protection_system import (
    CircuitBreaker,
    CircuitBreakerState,
    RateLimiter,
    RateLimitRule,
)


class TestRateLimiter:
    """Test suite for RateLimiter sliding window implementation."""

    def test_allows_under_limit(self):
        """Should allow requests under the limit."""
        limiter = RateLimiter()
        rule = RateLimitRule(requests=5, window=60, identifier="test")
        for _ in range(5):
            allowed, _ = limiter.is_allowed(rule, "user1")
            assert allowed is True

    def test_blocks_over_limit(self):
        """Should block when limit is exceeded."""
        limiter = RateLimiter()
        rule = RateLimitRule(requests=3, window=60, identifier="test")
        for _ in range(3):
            limiter.is_allowed(rule, "user1")
        allowed, info = limiter.is_allowed(rule, "user1")
        assert allowed is False
        assert info["remaining_requests"] == 0

    def test_separate_identifiers(self):
        """Different identifiers should have separate counters."""
        limiter = RateLimiter()
        rule = RateLimitRule(requests=2, window=60, identifier="test")
        limiter.is_allowed(rule, "user1")
        limiter.is_allowed(rule, "user1")
        allowed_u1, _ = limiter.is_allowed(rule, "user1")
        allowed_u2, _ = limiter.is_allowed(rule, "user2")
        assert allowed_u1 is False
        assert allowed_u2 is True

    def test_window_expiry(self):
        """Requests outside the window should not count."""
        limiter = RateLimiter()
        rule = RateLimitRule(requests=2, window=1, identifier="test")
        limiter.is_allowed(rule, "user1")
        limiter.is_allowed(rule, "user1")
        allowed, _ = limiter.is_allowed(rule, "user1")
        assert allowed is False

        # Wait for window to expire
        time.sleep(1.1)
        allowed, _ = limiter.is_allowed(rule, "user1")
        assert allowed is True

    def test_info_returns_correct_data(self):
        """is_allowed should return correct usage info."""
        limiter = RateLimiter()
        rule = RateLimitRule(requests=10, window=60, identifier="test")
        limiter.is_allowed(rule, "user1")
        limiter.is_allowed(rule, "user1")
        _, info = limiter.is_allowed(rule, "user1")
        assert info["requests_made"] == 2  # before this call
        assert info["requests_limit"] == 10

    def test_cleanup_removes_old_entries(self):
        """Cleanup should remove expired entries."""
        limiter = RateLimiter()
        rule = RateLimitRule(requests=10, window=1, identifier="test")
        limiter.is_allowed(rule, "user1")
        limiter.is_allowed(rule, "user2")
        time.sleep(1.1)
        limiter.cleanup_stale_entries(max_age=1)
        # After cleanup, histories should be gone
        assert len(limiter.request_history) == 0

    def test_get_stats(self):
        """get_stats should return valid statistics dict."""
        limiter = RateLimiter()
        rule = RateLimitRule(requests=10, window=60, identifier="test")
        limiter.is_allowed(rule, "user1")
        stats = limiter.get_stats()
        assert "active_identifiers" in stats
        assert stats["active_identifiers"] >= 1


class TestCircuitBreaker:
    """Test suite for CircuitBreaker pattern implementation."""

    def test_starts_closed(self):
        """Should start in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10)
        assert cb.state == CircuitBreakerState.CLOSED

    def test_opens_after_threshold(self):
        """Should open after failure threshold is reached."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10)
        cb._on_failure()
        cb._on_failure()
        cb._on_failure()
        assert cb.state == CircuitBreakerState.OPEN

    def test_success_resets_counter(self):
        """Recording a success should reset the failure counter."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10)
        cb._on_failure()
        cb._on_failure()
        cb._on_success()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.stats.failure_count == 0

    def test_half_open_after_timeout(self):
        """Should consider reset after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        cb._on_failure()
        cb._on_failure()
        assert cb.state == CircuitBreakerState.OPEN

        time.sleep(1.1)
        # After timeout, _should_attempt_reset should be True
        assert cb._should_attempt_reset() is True

    def test_get_stats(self):
        """get_stats should return complete stats dict."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10, name="test_cb")
        stats = cb.get_stats()
        assert stats["name"] == "test_cb"
        assert stats["state"] == "closed"
        assert stats["failure_threshold"] == 3

    def test_state_transitions_string_values(self):
        """CircuitBreakerState enum should have expected string values."""
        assert CircuitBreakerState.CLOSED.value == "closed"
        assert CircuitBreakerState.OPEN.value == "open"
        assert CircuitBreakerState.HALF_OPEN.value == "half_open"
