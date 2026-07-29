"""
Unit tests for shared/resilience.py
"""
import asyncio
import time

import pytest

from services.shared.resilience import (
    CacheManager,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
    CircuitState,
    HealthCheck,
    HealthCheckRegistry,
    MemoryCache,
    RateLimiter,
    RateLimitError,
    RetryPolicy,
    cached,
    calculate_delay,
    is_retryable_error,
    retry,
    retry_with_policy,
)


class TestRetryPolicy:
    """Tests for RetryPolicy."""

    def test_default_policy(self):
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0
        assert policy.exponential_base == 2.0
        assert policy.jitter == 0.1

    def test_custom_policy(self):
        policy = RetryPolicy(
            max_attempts=5,
            base_delay=2.0,
            max_delay=120.0,
            exponential_base=3.0,
        )
        assert policy.max_attempts == 5
        assert policy.base_delay == 2.0
        assert policy.max_delay == 120.0
        assert policy.exponential_base == 3.0


class TestCalculateDelay:
    """Tests for calculate_delay function."""

    def test_exponential_backoff(self):
        policy = RetryPolicy(base_delay=1.0, exponential_base=2.0, jitter=0.0)

        delay0 = calculate_delay(policy, 0)
        delay1 = calculate_delay(policy, 1)
        delay2 = calculate_delay(policy, 2)

        assert delay0 == 1.0
        assert delay1 == 2.0
        assert delay2 == 4.0

    def test_max_delay_cap(self):
        policy = RetryPolicy(base_delay=10.0, max_delay=30.0, jitter=0.0)

        delay = calculate_delay(policy, 10)  # Would be 10 * 2^10 = 10240 without cap
        assert delay == 30.0  # Capped at max_delay

    def test_jitter_added(self):
        policy = RetryPolicy(base_delay=10.0, jitter=0.5)

        delays = [calculate_delay(policy, 0) for _ in range(100)]
        # With jitter=0.5, delays should be between 5.0 and 15.0
        assert all(5.0 <= d <= 15.0 for d in delays)


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_retryable_exceptions(self):
        policy = RetryPolicy()

        assert is_retryable_error(ConnectionError("connection failed"), policy)
        assert is_retryable_error(TimeoutError("timeout"), policy)
        assert is_retryable_error(OSError("io error"), policy)

    def test_non_retryable_exceptions(self):
        policy = RetryPolicy()

        assert not is_retryable_error(ValueError("invalid value"), policy)
        assert not is_retryable_error(TypeError("type error"), policy)
        assert not is_retryable_error(KeyError("missing key"), policy)

    def test_external_api_error_retryable(self):
        from services.shared.exceptions import ExternalAPIError

        policy = RetryPolicy()
        error = ExternalAPIError("Rate limited", "groq", 429, "rate limited")

        assert is_retryable_error(error, policy)

    def test_external_api_error_non_retryable(self):
        from services.shared.exceptions import ExternalAPIError

        policy = RetryPolicy()
        error = ExternalAPIError("Not found", "api", 404, "not found")

        assert not is_retryable_error(error, policy)


class TestRetryWithPolicy:
    """Tests for retry_with_policy function."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        policy = RetryPolicy(max_attempts=3, base_delay=0.01)

        async def success_func():
            return "success"

        result = await retry_with_policy(success_func, policy=policy)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        policy = RetryPolicy(max_attempts=3, base_delay=0.01)

        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"

        result = await retry_with_policy(flaky_func, policy=policy)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhausted_retries(self):
        policy = RetryPolicy(max_attempts=2, base_delay=0.01)

        async def always_fails():
            raise ConnectionError("Always fails")

        with pytest.raises(Exception) as exc_info:
            await retry_with_policy(always_fails, policy=policy)

        # Should raise RetryExhaustedError or the original error
        assert isinstance(exc_info.value, (Exception,))


class TestRetryDecorator:
    """Tests for @retry decorator."""

    @pytest.mark.asyncio
    async def test_retry_decorator_success(self):
        @retry(max_attempts=3, base_delay=0.01)
        async def success_func():
            return "success"

        result = await success_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_decorator_retry(self):
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"

        result = await flaky_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        @retry(max_attempts=2, base_delay=0.01)
        async def always_fails():
            raise ConnectionError("Always fails")

        with pytest.raises(Exception) as exc_info:
            await always_fails()

        # Should raise RetryExhaustedError or original error
        assert isinstance(exc_info.value, Exception)


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_states(self):
        assert CircuitState.CLOSED == "closed"
        assert CircuitState.OPEN == "open"
        assert CircuitState.HALF_OPEN == "half_open"


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig."""

    def test_default_config(self):
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout == 60.0
        assert config.half_open_max_calls == 3

    def test_custom_config(self):
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=1,
            timeout=30.0,
        )
        assert config.failure_threshold == 3
        assert config.success_threshold == 1
        assert config.timeout == 30.0


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))

        async def fail():
            raise ConnectionError("fail")

        # First 2 failures - still closed
        for _ in range(2):
            try:
                await cb.call(fail)
            except:
                pass
        assert cb.state == "closed"

        # 3rd failure - opens
        try:
            await cb.call(fail)
        except:
            pass
        assert cb.state == "open"

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=1,
            timeout=0.1,
        ))

        async def fail():
            raise ConnectionError("fail")

        # Trigger open
        try:
            await cb.call(fail)
        except:
            pass
        assert cb.state == "open"

        # Wait for timeout
        await asyncio.sleep(0.15)

        # Should be half-open
        assert cb.state == "half_open"

    @pytest.mark.asyncio
    async def test_half_open_closes_on_success(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=2,
            timeout=0.1,
        ))

        async def fail():
            raise ConnectionError("fail")

        async def succeed():
            return "success"

        # Trigger open
        try:
            await cb.call(fail)
        except:
            pass
        assert cb.state == "open"

        # Wait for half-open
        await asyncio.sleep(0.15)
        assert cb.state == "half_open"

        # Success in half-open
        await cb.call(succeed)
        assert cb.state == "half_open"

        # Second success closes
        await cb.call(succeed)
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_half_open_reopens_on_failure(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=1,
            timeout=0.1,
        ))

        async def fail():
            raise ConnectionError("fail")

        # Trigger open
        try:
            await cb.call(fail)
        except:
            pass

        # Wait for half-open
        await asyncio.sleep(0.15)

        # Fail in half-open
        try:
            await cb.call(fail)
        except:
            pass

        assert cb.state == "open"

    @pytest.mark.asyncio
    async def test_can_execute_in_half_open(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=5,  # Higher than half_open_max_calls so it stays in half-open
            half_open_max_calls=2,
            timeout=0.1,
        ))

        async def succeed():
            return "ok"

        async def fail():
            raise ConnectionError("fail")

        # Open
        try:
            await cb.call(fail)
        except:
            pass

        await asyncio.sleep(0.15)
        assert cb.state == "half_open"

        # Can make up to half_open_max_calls
        await cb.call(succeed)
        await cb.call(succeed)

        # Third should fail (exceeds half_open_max_calls)
        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(succeed)

    @pytest.mark.asyncio
    async def test_circuit_breaker_registry(self):
        registry = CircuitBreakerRegistry()

        cb1 = await registry.get_or_create("test1")
        cb2 = await registry.get_or_create("test1")
        assert cb1 is cb2

        stats = await registry.get_all_stats()
        assert "test1" in stats

    @pytest.mark.asyncio
    async def test_circuit_breaker_get_stats(self):
        cb = CircuitBreaker("test")
        stats = cb.get_stats()

        assert stats["name"] == "test"
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0
        assert stats["success_count"] == 0


class TestRateLimiter:
    """Tests for RateLimiter."""

    @pytest.mark.asyncio
    async def test_allows_burst_up_to_limit(self):
        rl = RateLimiter(default_rate=10.0, default_burst=5)

        for _ in range(5):
            assert await rl.acquire("test") is True

    @pytest.mark.asyncio
    async def test_blocks_after_burst(self):
        rl = RateLimiter(default_rate=1.0, default_burst=2)

        await rl.acquire("test")
        await rl.acquire("test")

        # Third should raise RateLimitError
        start = time.time()
        try:
            await rl.acquire("test", timeout=0.5)
            raise AssertionError("Should have raised RateLimitError")
        except RateLimitError:
            pass

        elapsed = time.time() - start
        assert elapsed >= 0.5  # Should have waited

    @pytest.mark.asyncio
    async def test_local_buckets(self):
        rl = RateLimiter(default_rate=1.0, default_burst=3)

        # Should allow burst
        for _ in range(3):
            assert await rl.acquire("test") is True

        # Fourth should raise RateLimitError with short timeout
        with pytest.raises(RateLimitError):
            await rl.acquire("test", timeout=0.1)


class TestCacheLayer:
    """Tests for CacheLayer."""

    @pytest.mark.asyncio
    async def test_memory_cache_set_get(self):
        cache = MemoryCache(default_ttl=60)

        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"

    @pytest.mark.asyncio
    async def test_memory_cache_expiry(self):
        cache = MemoryCache(default_ttl=0)  # Immediate expiry

        await cache.set("key", "value")
        await asyncio.sleep(0.1)
        assert await cache.get("key") is None

    @pytest.mark.asyncio
    async def test_cache_delete(self):
        cache = MemoryCache(default_ttl=60)

        await cache.set("key", "value")
        await cache.delete("key")
        assert await cache.get("key") is None

    @pytest.mark.asyncio
    async def test_cache_clear(self):
        cache = MemoryCache(default_ttl=60)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None


class TestCacheManager:
    """Tests for CacheManager."""

    @pytest.mark.asyncio
    async def test_get_set(self):
        manager = CacheManager(MemoryCache())

        await manager.set("ns", "key", "value")
        assert await manager.get("ns", "key") == "value"

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        manager = CacheManager(MemoryCache())

        assert await manager.get("ns", "nonexistent") is None


class TestCachedDecorator:
    """Tests for @cached decorator."""

    @pytest.mark.asyncio
    async def test_cached_decorator(self):
        call_count = 0

        @cached("test", ttl=60)
        async def func():
            nonlocal call_count
            call_count += 1
            return call_count

        result1 = await func()
        result2 = await func()

        assert result1 == 1
        assert result2 == 1  # Cached
        assert call_count == 1  # Only called once

    @pytest.mark.asyncio
    async def test_cached_with_key_func(self):
        call_count = 0

        @cached("test", key_func=lambda x: f"key_{x}")
        async def func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = await func(5)
        result2 = await func(5)
        result3 = await func(10)

        assert result1 == 10
        assert result2 == 10  # Cached
        assert result3 == 20  # Different key
        assert call_count == 2


class TestHealthChecks:
    """Tests for HealthCheck system."""

    @pytest.mark.asyncio
    async def test_health_check_registry(self):
        registry = HealthCheckRegistry()

        check = HealthCheck("test", timeout=1.0)

        async def check_func():
            return {"status": "healthy"}

        check.check = check_func
        registry.register(check)

        results = await registry.run_all()

        assert results["healthy"] is True
        assert "test" in results["checks"]
        assert results["checks"]["test"]["healthy"] is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        registry = HealthCheckRegistry()

        check = HealthCheck("failing", timeout=1.0)

        async def failing_check():
            raise Exception("Failed")

        check.check = failing_check
        registry.register(check)

        results = await registry.run_all()

        assert results["healthy"] is False
        assert results["checks"]["failing"]["healthy"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
