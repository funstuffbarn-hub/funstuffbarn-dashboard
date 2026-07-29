#!/usr/bin/env python3
"""
shared/__init__.py - Shared types and utilities for FunStuffBarn microservices
"""

from .config import Settings, get_settings
from .exceptions import (
    AgentError,
    CircuitBreakerOpenError,
    ExternalAPIError,
    RateLimitError,
    ValidationError,
)
from .logging import correlation_id_var, get_logger, log_execution_time, setup_logging
from .models import (
    AgentResult,
    AgentStatus,
    CreativeReport,
    DesignConcept,
    ListingData,
    MarketAnalysisReport,
    PinterestReport,
    SalesMetrics,
    StoreReport,
    StrategyReport,
)
from .resilience import (
    CacheLayer,
    CircuitBreaker,
    RateLimiter,
    retry_with_policy,
)

__all__ = [
    # Config
    "Settings",
    "get_settings",
    # Models
    "AgentResult",
    "AgentStatus",
    "MarketAnalysisReport",
    "CreativeReport",
    "StoreReport",
    "PinterestReport",
    "StrategyReport",
    "DesignPrompt",
    "ListingData",
    "SalesMetrics",
    # Exceptions
    "AgentError",
    "ExternalAPIError",
    "ValidationError",
    "CircuitBreakerOpenError",
    "RateLimitError",
    # Resilience
    "retry_with_policy",
    "CircuitBreaker",
    "RateLimiter",
    "CacheLayer",
    # Logging
    "setup_logging",
    "get_logger",
    "correlation_id_var",
    "log_execution_time",
]
