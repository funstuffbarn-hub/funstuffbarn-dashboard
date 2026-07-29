"""
Custom exceptions for the FunStuffBarn agent system.
"""
from typing import Any
from uuid import UUID


class AgentError(Exception):
    """Base exception for agent-related errors."""

    def __init__(
        self,
        message: str,
        agent_type: str | None = None,
        correlation_id: UUID = None,
        details: dict[str, Any] | None = None,
        recoverable: bool = False,
    ):
        super().__init__(message)
        self.message = message
        self.agent_type = agent_type
        self.correlation_id = correlation_id
        self.details = details or {}
        self.recoverable = recoverable

    def __str__(self) -> str:
        parts = [self.message]
        if self.agent_type:
            parts.append(f"Agent: {self.agent_type}")
        if self.correlation_id:
            parts.append(f"Correlation: {self.correlation_id}")
        return " | ".join(parts)


class ExternalAPIError(AgentError):
    """Error from external API calls (Groq, Etsy, Printful, etc.)."""

    def __init__(
        self,
        message: str,
        api_name: str,
        status_code: int | None = None,
        response_body: str | None = None,
        correlation_id: UUID = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            agent_type=api_name,
            correlation_id=correlation_id,
            details={
                "status_code": status_code,
                "response_body": response_body,
            },
            recoverable=True,
            **kwargs
        )
        self.api_name = api_name
        self.status_code = status_code
        self.response_body = response_body


class ValidationError(AgentError):
    """Data validation error."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        correlation_id: UUID = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            correlation_id=correlation_id,
            details={"field": field, "value": str(value) if value is not None else None},
            recoverable=False,
            **kwargs
        )
        self.field = field
        self.value = value

    def __str__(self) -> str:
        parts = [self.message]
        if self.field:
            parts.append(f"field: {self.field}")
        return " | ".join(parts)


class CircuitBreakerOpenError(AgentError):
    """Raised when circuit breaker is open."""

    def __init__(
        self,
        service_name: str,
        reset_timeout: float,
        correlation_id: UUID = None,
        **kwargs
    ):
        super().__init__(
            message=f"Circuit breaker open for {service_name}. Retry after {reset_timeout}s.",
            agent_type=service_name,
            correlation_id=correlation_id,
            details={
                "service": service_name,
                "reset_timeout": reset_timeout,
            },
            recoverable=True,
            **kwargs
        )
        self.service_name = service_name
        self.reset_timeout = reset_timeout


class RateLimitError(AgentError):
    """Rate limit exceeded error."""

    def __init__(
        self,
        service: str,
        retry_after: float,
        correlation_id: UUID = None,
        **kwargs
    ):
        super().__init__(
            message=f"Rate limit exceeded for {service}. Retry after {retry_after}s.",
            agent_type=service,
            correlation_id=correlation_id,
            details={
                "service": service,
                "retry_after": retry_after,
            },
            recoverable=True,
            **kwargs
        )
        self.service = service
        self.retry_after = retry_after


class ConfigurationError(AgentError):
    """Configuration error."""

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        correlation_id: UUID = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            correlation_id=correlation_id,
            details={"config_key": config_key},
            recoverable=False,
        )
        self.config_key = config_key

    def __str__(self):
        if self.config_key:
            return f"{self.message} (config_key: {self.config_key})"
        return self.message


class RetryExhaustedError(AgentError):
    """All retry attempts exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_exception: Exception | None = None,
        correlation_id: UUID = None,
        **kwargs
    ):
        details = {"attempts": attempts}
        if last_exception:
            details["last_error"] = str(last_exception)

        super().__init__(
            message=message,
            correlation_id=correlation_id,
            details=details,
            recoverable=False,
        )
        self.attempts = attempts
        self.last_exception = last_exception


class TimeoutError(AgentError):
    """Operation timeout error."""

    def __init__(
        self,
        message: str,
        timeout: float,
        operation: str,
        correlation_id: UUID = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            correlation_id=correlation_id,
            details={"timeout": timeout, "operation": operation},
            recoverable=True,
        )
        self.timeout = timeout
        self.operation = operation

    def __str__(self) -> str:
        parts = [self.message]
        if self.operation:
            parts.append(f"operation: {self.operation}")
        return " | ".join(parts)
