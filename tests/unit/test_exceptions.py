"""
Unit tests for shared/exceptions.py
"""
import pytest
from uuid import uuid4, UUID
from datetime import datetime

from services.shared.exceptions import (
    AgentError,
    ExternalAPIError,
    ValidationError,
    CircuitBreakerOpenError,
    RateLimitError,
    ConfigurationError,
    RetryExhaustedError,
    TimeoutError,
)


class TestAgentError:
    """Tests for AgentError base class."""
    
    def test_agent_error_creation(self):
        error = AgentError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.agent_type is None
        assert error.correlation_id is None
        assert error.details == {}
        assert error.recoverable is False
    
    def test_agent_error_with_all_fields(self):
        corr_id = uuid4()
        error = AgentError(
            message="Test error",
            agent_type="mercado",
            correlation_id=corr_id,
            details={"key": "value"},
            recoverable=True,
        )
        assert error.message == "Test error"
        assert error.agent_type == "mercado"
        assert error.correlation_id == corr_id
        assert error.details == {"key": "value"}
        assert error.recoverable is True
    
    def test_str_representation(self):
        corr_id = uuid4()
        error = AgentError("Test", agent_type="mercado", correlation_id=corr_id)
        str_repr = str(error)
        assert "Test" in str_repr
        assert "mercado" in str_repr
        assert str(corr_id) in str_repr


class TestExternalAPIError:
    """Tests for ExternalAPIError."""
    
    def test_external_api_error_creation(self):
        error = ExternalAPIError(
            message="API failed",
            api_name="groq",
            status_code=429,
            response_body="Rate limit exceeded",
        )
        assert error.message == "API failed"
        assert error.api_name == "groq"
        assert error.status_code == 429
        assert error.response_body == "Rate limit exceeded"
        assert error.recoverable is True
    
    def test_str_representation(self):
        error = ExternalAPIError("Failed", "groq", 429, "rate limited")
        str_repr = str(error)
        assert "Failed" in str_repr
        assert "groq" in str_repr


class TestValidationError:
    """Tests for ValidationError."""
    
    def test_validation_error_creation(self):
        error = ValidationError(
            message="Invalid field",
            field="email",
            value="invalid-email",
        )
        assert error.message == "Invalid field"
        assert error.field == "email"
        assert error.value == "invalid-email"
        assert error.recoverable is False
    
    def test_str_representation(self):
        error = ValidationError("Invalid", field="email", value="bad")
        str_repr = str(error)
        assert "Invalid" in str_repr
        assert "email" in str_repr


class TestCircuitBreakerOpenError:
    """Tests for CircuitBreakerOpenError."""
    
    def test_creation(self):
        error = CircuitBreakerOpenError("groq", 60.0)
        assert "groq" in str(error)
        assert error.service_name == "groq"
        assert error.reset_timeout == 60.0
        assert error.recoverable is True
    
    def test_with_correlation_id(self):
        corr_id = uuid4()
        error = CircuitBreakerOpenError("groq", 60.0, correlation_id=corr_id)
        assert error.correlation_id == corr_id


class TestRateLimitError:
    """Tests for RateLimitError."""
    
    def test_creation(self):
        error = RateLimitError("groq", 30.0)
        assert "groq" in str(error)
        assert error.service == "groq"
        assert error.retry_after == 30.0
        assert error.recoverable is True
    
    def test_str_representation(self):
        error = RateLimitError("etsy", 15.5)
        str_repr = str(error)
        assert "etsy" in str_repr
        assert "15.5" in str_repr


class TestConfigurationError:
    """Tests for ConfigurationError."""
    
    def test_creation(self):
        error = ConfigurationError("Missing config", config_key="API_KEY")
        assert error.message == "Missing config"
        assert error.config_key == "API_KEY"
        assert error.recoverable is False
    
    def test_str_representation(self):
        error = ConfigurationError("Missing", config_key="API_KEY")
        str_repr = str(error)
        assert "Missing" in str_repr
        assert "API_KEY" in str_repr


class TestRetryExhaustedError:
    """Tests for RetryExhaustedError."""
    
    def test_creation(self):
        last_exc = ValueError("test error")
        error = RetryExhaustedError(
            message="All retries failed",
            attempts=3,
            last_exception=last_exc,
        )
        assert error.message == "All retries failed"
        assert error.attempts == 3
        assert error.last_exception == last_exc
        assert error.recoverable is False
    
    def test_str_representation(self):
        error = RetryExhaustedError("Failed", 5, ValueError("test"))
        str_repr = str(error)
        assert "Failed" in str_repr


class TestTimeoutError:
    """Tests for TimeoutError."""
    
    def test_creation(self):
        error = TimeoutError(
            message="Operation timed out",
            timeout=30.0,
            operation="api_call",
        )
        assert error.message == "Operation timed out"
        assert error.timeout == 30.0
        assert error.operation == "api_call"
        assert error.recoverable is True
    
    def test_str_representation(self):
        error = TimeoutError("Timeout", 10.0, "api_call")
        str_repr = str(error)
        assert "Timeout" in str_repr
        assert "api_call" in str_repr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])