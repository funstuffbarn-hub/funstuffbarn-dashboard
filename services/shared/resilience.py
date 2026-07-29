"""
Resilience utilities: retry logic, circuit breaker, rate limiting, and caching.
"""
import asyncio
import builtins
import logging
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, TypeVar

import redis.asyncio as redis

from .exceptions import (
    CircuitBreakerOpenError,
    ExternalAPIError,
    RateLimitError,
    RetryExhaustedError,
    TimeoutError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================
# Retry Logic
# ============================================================

@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: float = 0.1
    retryable_exceptions: tuple = (
        ConnectionError,
        TimeoutError,
        IOError,
        ExternalAPIError,
    )
    retryable_status_codes: set = frozenset({408, 429, 500, 502, 503, 504})
    retryable_keywords: set = frozenset()
    non_retryable_status_codes: set = frozenset({400, 401, 403, 404})


def calculate_delay(policy: RetryPolicy, attempt: int) -> float:
    """Calculate delay with exponential backoff and jitter."""
    delay = min(
        policy.base_delay * (policy.exponential_base ** attempt) +
        random.uniform(0, policy.jitter),
        policy.max_delay
    )
    return delay


def is_retryable_error(error: Exception, policy: RetryPolicy) -> bool:
    """Determine if an error is retryable."""
    # Check ExternalAPIError first for status code logic
    if isinstance(error, ExternalAPIError):
        if error.status_code in policy.non_retryable_status_codes:
            return False
        return error.status_code in policy.retryable_status_codes
    # Then check other retryable exceptions
    if isinstance(error, policy.retryable_exceptions):
        return True
    return False


# Predefined retry policies for external services
GROQ_POLICY = RetryPolicy(
    max_attempts=3,
    base_delay=5.0,
    max_delay=60.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
    retryable_status_codes={429, 500, 502, 503, 504},
    retryable_keywords={'rate limit', 'too many requests', 'tokens per minute', 'tpm'}
)

ETSY_POLICY = RetryPolicy(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
    retryable_status_codes={429, 500, 502, 503, 504},
    retryable_keywords={'rate limit', 'too many requests', 'service unavailable'}
)

TRENDS_POLICY = RetryPolicy(
    max_attempts=3,
    base_delay=5.0,
    max_delay=60.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
    retryable_status_codes={429, 500, 502, 503, 504},
    retryable_keywords={'rate limit', 'too many requests', 'service unavailable'}
)

PRINTFUL_POLICY = RetryPolicy(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
    retryable_status_codes={429, 500, 502, 503, 504},
    retryable_keywords={'rate limit', 'too many requests', 'service unavailable'}
)

TRENDS_POLICY = RetryPolicy(
    max_attempts=3,
    base_delay=5.0,
    max_delay=60.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
    retryable_status_codes={429, 500, 502, 503, 504},
    retryable_keywords={'rate limit', 'too many requests', 'service unavailable'}
)

PINTEREST_POLICY = RetryPolicy(
    max_attempts=2,
    base_delay=3.0,
    max_delay=30.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
    retryable_status_codes={429, 500, 502, 503, 504},
    retryable_keywords={'rate limit', 'too many requests', 'service unavailable'}
)

EMAIL_POLICY = RetryPolicy(
    max_attempts=3,
    base_delay=10.0,
    max_delay=120.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
    retryable_keywords={'connection', 'timeout', 'dns', 'resolve', 'temporary failure'}
)


async def retry_with_policy(
    func: Callable[..., T],
    *args,
    policy: RetryPolicy | None = None,
    on_retry: Callable[[Exception, int], None] | None = None,
    **kwargs
) -> T:
    """Execute function with retry policy."""
    policy = policy or RetryPolicy()
    last_exception = None

    for attempt in range(policy.max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if not is_retryable_error(e, policy) or attempt >= policy.max_attempts:
                raise

            delay = calculate_delay(policy, attempt)
            logger.warning(
                f"Attempt {attempt + 1}/{policy.max_attempts + 1} failed: {e}. "
                f"Retrying in {delay:.1f}s..."
            )

            if on_retry:
                on_retry(e, attempt + 1)

            await asyncio.sleep(delay)

    raise RetryExhaustedError(
        message=f"All {policy.max_attempts + 1} attempts failed",
        attempts=policy.max_attempts + 1,
        last_exception=last_exception,
    )


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: tuple = (ConnectionError, TimeoutError, IOError, ExternalAPIError),
):
    """Decorator for automatic retry with exponential backoff."""
    policy = RetryPolicy(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_policy(func, *args, policy=policy, **kwargs)
        return wrapper
    return decorator


# ============================================================
# Circuit Breaker
# ============================================================

class CircuitState:
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5          # Failures before opening
    success_threshold: int = 2          # Successes to close from half-open
    timeout: float = 60.0               # Seconds before half-open
    half_open_max_calls: int = 3        # Max calls in half-open state
    excluded_exceptions: tuple = ()     # Exceptions that don't count as failures


class CircuitBreaker:
    """Thread-safe circuit breaker implementation."""

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        """Get current state, checking for timeout transition."""
        if self._state == CircuitState.OPEN:
            if (self._last_failure_time and
                datetime.utcnow() - self._last_failure_time > timedelta(seconds=self.config.timeout)):
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                return CircuitState.HALF_OPEN
        return self._state

    @state.setter
    def state(self, value: str):
        self._state = value

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function through circuit breaker."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(self.name, self.config.timeout)

            if self.state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpenError(self.name, self.config.timeout)
                self._half_open_calls += 1

        try:
            result = await func()
        except Exception as e:
            await self._record_failure(e)
            raise

        await self._record_success()
        return result

    async def _record_failure(self, error: Exception):
        async with self._lock:
            # Check if exception should be ignored
            if isinstance(error, self.config.excluded_exceptions):
                return

            self._failure_count += 1
            self._last_failure_time = datetime.utcnow()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open opens circuit
                self._state = CircuitState.OPEN
                self._success_count = 0
                logger.warning(f"Circuit breaker {self.name} opened after half-open failure")
            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit breaker {self.name} opened after {self._failure_count} failures")

    async def _record_success(self):
        async with self._lock:
            self._failure_count = 0

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._success_count = 0
                    self._half_open_calls = 0
                    logger.info(f"Circuit breaker {self.name} closed after recovery")
            elif self._state == CircuitState.CLOSED:
                self._half_open_calls = 0

    def reset(self):
        """Manually reset circuit breaker."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time = None
        logger.info(f"Circuit breaker {self.name} manually reset")

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "half_open_calls": self._half_open_calls,
            "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
        }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker."""
        async with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]

    async def get(self, name: str) -> CircuitBreaker | None:
        """Get existing circuit breaker."""
        return self._breakers.get(name)

    async def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all circuit breakers."""
        return {name: cb.get_stats() for name, cb in self._breakers.items()}

    async def reset_all(self):
        """Reset all circuit breakers."""
        for cb in self._breakers.values():
            cb.reset()


# Global registry
circuit_breaker_registry = CircuitBreakerRegistry()


# ============================================================
# Rate Limiter
# ============================================================

class RateLimiter:
    """Token bucket rate limiter with Redis backend."""

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        default_rate: float = 10.0,  # requests per second
        default_burst: int = 20
    ):
        self.redis = redis_client
        self.default_rate = default_rate
        self.default_burst = default_burst
        self._local_buckets: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def acquire(
        self,
        key: str,
        rate: float | None = None,
        burst: int | None = None,
        tokens: int = 1,
        timeout: float = 30.0
    ) -> bool:
        """
        Acquire tokens from rate limiter.
        Returns True if acquired, raises RateLimitError on timeout.
        """
        rate = rate or self.default_rate
        burst = burst or self.default_burst

        start_time = time.time()

        while time.time() - start_time < timeout:
            acquired = await self._try_acquire(key, rate, burst, tokens)
            if acquired:
                return True

            # Wait for token refill
            wait_time = min(1.0 / rate, 0.1)
            await asyncio.sleep(wait_time)

        raise RateLimitError(key, timeout)

    async def _try_acquire(self, key: str, rate: float, burst: int, tokens: int) -> bool:
        """Try to acquire tokens. Returns True if successful."""
        if self.redis:
            return await self._acquire_redis(key, rate, burst, tokens)
        else:
            return await self._acquire_local(key, rate, burst, tokens)

    async def _acquire_redis(self, key: str, rate: float, burst: int, tokens: int) -> bool:
        """Redis-based token bucket."""
        now = time.time()
        key_prefix = f"ratelimit:{key}"

        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local rate = tonumber(ARGV[2])
        local burst = tonumber(ARGV[3])
        local tokens = tonumber(ARGV[4])

        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens_available = tonumber(bucket[1]) or burst
        local last_refill = tonumber(bucket[2]) or now

        -- Refill tokens
        local elapsed = now - last_refill
        tokens_available = math.min(burst, tokens_available + elapsed * rate)

        if tokens_available >= tokens then
            tokens_available = tokens_available - tokens
            redis.call('HMSET', key, 'tokens', tokens_available, 'last_refill', now)
            redis.call('EXPIRE', key, math.ceil(burst / rate) + 10)
            return 1
        else
            redis.call('HMSET', key, 'tokens', tokens_available, 'last_refill', now)
            redis.call('EXPIRE', key, math.ceil(burst / rate) + 10)
            return 0
        end
        """

        result = await self.redis.eval(
            lua_script, 1, key_prefix,
            now, rate, burst, tokens
        )
        return bool(result)

    async def _acquire_local(self, key: str, rate: float, burst: int, tokens: int) -> bool:
        """In-memory token bucket (fallback)."""
        async with self._lock:
            now = time.time()

            if key not in self._local_buckets:
                self._local_buckets[key] = {
                    "tokens": float(burst),
                    "last_refill": now,
                }

            bucket = self._local_buckets[key]
            elapsed = now - bucket["last_refill"]
            bucket["tokens"] = min(burst, bucket["tokens"] + elapsed * rate)
            bucket["last_refill"] = now

            if bucket["tokens"] >= tokens:
                bucket["tokens"] -= tokens
                return True
            return False


# ============================================================
# Cache Layer
# ============================================================

class CacheBackend(ABC):
    """Abstract cache backend."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int) -> None:
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        pass

    @abstractmethod
    async def clear(self) -> None:
        pass


class RedisCache(CacheBackend):
    """Redis cache backend."""

    def __init__(self, redis_client: redis.Redis, default_ttl: int = 3600):
        self.redis = redis_client
        self.default_ttl = default_ttl

    async def get(self, key: str) -> Any | None:
        data = await self.redis.get(key)
        if data:
            import json
            return json.loads(data)
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        import json
        await self.redis.setex(key, ttl or self.default_ttl, json.dumps(value))

    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

    async def clear(self) -> None:
        await self.redis.flushdb()


class MemoryCache(CacheBackend):
    """In-memory cache backend (for testing/local dev)."""

    def __init__(self, default_ttl: int = 3600):
        self._cache: dict[str, tuple] = {}  # (value, expiry)
        self.default_ttl = default_ttl
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if datetime.utcnow() < expiry:
                    return value
                del self._cache[key]
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        async with self._lock:
            expiry = datetime.utcnow() + timedelta(seconds=ttl or self.default_ttl)
            self._cache[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()


class CacheManager:
    """High-level cache manager with namespaces."""

    def __init__(self, backend: CacheBackend, default_ttl: int = 3600):
        self.backend = backend
        self.default_ttl = default_ttl

    def _make_key(self, namespace: str, key: str) -> str:
        return f"{namespace}:{key}"

    async def get(self, namespace: str, key: str) -> Any | None:
        return await self.backend.get(self._make_key(namespace, key))

    async def set(self, namespace: str, key: str, value: Any, ttl: int | None = None) -> None:
        await self.backend.set(self._make_key(namespace, key), value, ttl or self.default_ttl)

    async def delete(self, namespace: str, key: str) -> None:
        await self.backend.delete(self._make_key(namespace, key))

    async def clear_namespace(self, namespace: str) -> None:
        # For Redis, would need pattern matching
        # For memory, we can iterate
        pass


class CacheLayer:
    """Alias for CacheManager for backward compatibility."""

    def __init__(self, backend: CacheBackend, default_ttl: int = 3600):
        self.manager = CacheManager(backend, default_ttl)

    async def get(self, namespace: str, key: str) -> Any | None:
        return await self.manager.get(namespace, key)

    async def set(self, namespace: str, key: str, value: Any, ttl: int | None = None) -> None:
        await self.manager.set(namespace, key, value, ttl)

    async def delete(self, namespace: str, key: str) -> None:
        await self.manager.delete(namespace, key)

    async def clear(self, namespace: str) -> None:
        pass


class SafeCache:
    """Cache that safely handles unhashable keys by converting them to JSON strings."""

    def __init__(self, backend: CacheBackend, default_ttl: int = 3600):
        self.manager = CacheManager(backend, default_ttl)

    def _safe_key(self, key: Any) -> str:
        """Convert unhashable key to a hashable JSON string."""
        try:
            hash(key)
            return key
        except TypeError:
            import json
            return json.dumps(key, sort_keys=True, default=str)

    async def get(self, namespace: str, key: Any) -> Any | None:
        return await self.manager.get(namespace, self._safe_key(key))

    async def set(self, namespace: str, key: Any, value: Any, ttl: int | None = None) -> None:
        await self.manager.set(namespace, self._safe_key(key), value, ttl)

    async def delete(self, namespace: str, key: Any) -> None:
        await self.manager.delete(namespace, self._safe_key(key))

    async def clear(self, namespace: str) -> None:
        pass


# ============================================================
# Decorators
# ============================================================

def cached(
    namespace: str,
    ttl: int = 3600,
    key_func: Callable[..., str] | None = None,
):
    """Decorator for caching function results."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()

            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: function name + args
                cache_key = f"{func.__name__}:{hash((args, frozenset(kwargs.items())))}"

            # Try cache
            cached = await cache_manager.get(func.__module__, func.__name__ + ":" + cache_key)
            if cached is not None:
                return cached

            # Execute and cache
            result = await func(*args, **kwargs)
            await cache_manager.set(func.__module__, func.__name__ + ":" + cache_key, result)
            return result
        return wrapper
    return decorator


# Global cache manager instance
_cache_manager: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    global _cache_manager
    if _cache_manager is None:
        # Default to memory cache
        _cache_manager = CacheManager(MemoryCache())
    return _cache_manager


def set_cache_manager(manager: CacheManager):
    global _cache_manager
    _cache_manager = manager


# ============================================================
# Health Checks
# ============================================================

class HealthCheck:
    """Base class for health checks."""

    def __init__(self, name: str, timeout: float = 5.0):
        self.name = name
        self.timeout = timeout

    @abstractmethod
    async def check(self) -> dict[str, Any]:
        """Perform health check. Return dict with status and details."""
        pass


class HealthCheckRegistry:
    """Registry for health checks."""

    def __init__(self):
        self._checks: list[HealthCheck] = []

    def register(self, check: HealthCheck):
        self._checks.append(check)

    async def run_all(self) -> dict[str, Any]:
        """Run all health checks."""
        results = {}
        overall_healthy = True

        for check in self._checks:
            try:
                result = await asyncio.wait_for(check.check(), timeout=check.timeout)
                results[check.name] = {"healthy": True, **result}
            except builtins.TimeoutError:
                results[check.name] = {"healthy": False, "error": "Timeout"}
                overall_healthy = False
            except Exception as e:
                results[check.name] = {"healthy": False, "error": str(e)}
                overall_healthy = False

        return {
            "healthy": overall_healthy,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": results,
        }


# Global registry
health_registry = HealthCheckRegistry()
