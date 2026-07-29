"""
Unit tests for shared/logging.py
"""
import asyncio
import logging
import pytest
import json
import time
from unittest.mock import Mock, patch
from io import StringIO

from services.shared.logging import (
    setup_logging,
    get_logger,
    get_correlation_id,
    set_correlation_id,
    CorrelationIdFilter,
    JSONFormatter,
    LoggingContext,
    log_execution_time,
)


class TestCorrelationId:
    """Tests for correlation ID management."""
    
    def test_get_correlation_id_generates_new(self):
        """Test that get_correlation_id generates a new ID when none exists."""
        # Clear any existing
        import services.shared.logging as logging_module
        logging_module.correlation_id_var.set(None)
        
        cid = get_correlation_id()
        assert cid is not None
        assert len(cid) == 36  # UUID length with hyphens
    
    def test_set_correlation_id(self):
        """Test setting a specific correlation ID."""
        cid = set_correlation_id("test-correlation-id")
        assert cid == "test-correlation-id"
        assert get_correlation_id() == "test-correlation-id"
    
    def test_set_correlation_id_generates_when_none(self):
        """Test that set_correlation_id generates when None provided."""
        cid = set_correlation_id(None)
        assert cid is not None
        assert get_correlation_id() == cid


class TestCorrelationIdFilter:
    """Tests for CorrelationIdFilter."""
    
    def test_filter_adds_correlation_id(self):
        filter_obj = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        
        # Set a correlation ID
        set_correlation_id("test-correlation-id")
        
        result = filter_obj.filter(record)
        assert result is True
        assert record.correlation_id == "test-correlation-id"
    
    def test_filter_generates_when_none(self):
        """Test that filter generates correlation ID when none set."""
        import services.shared.logging as logging_module
        logging_module.correlation_id_var.set(None)
        
        filter_obj = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        
        result = filter_obj.filter(record)
        assert result is True
        assert record.correlation_id is not None


class TestJSONFormatter:
    """Tests for JSONFormatter."""
    
    def test_formats_basic_fields(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.created = 1234567890.0
        record.msecs = 500
        record.levelname = "INFO"
        record.levelno = 20
        record.funcName = "<module>"
        
        log_record = {}
        formatter.add_fields(log_record, record, {})
        
        assert log_record["timestamp"] is not None
        assert log_record["level"] == "INFO"
        assert log_record["logger"] == "test.logger"
        assert log_record["message"] == "Test message"
        assert log_record["module"] == "test"
        assert log_record["function"] == "<module>"
        assert log_record["line"] == 42
        assert "correlation_id" in log_record
    
    def test_formats_exception(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("Test error")
        except ValueError as e:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="Error occurred",
                args=(),
                exc_info=(type(e), e, e.__traceback__),
            )
        
        log_record = {}
        formatter.add_fields(log_record, record, {})
        
        assert "exception" in log_record
        assert "ValueError: Test error" in log_record["exception"]
    
    def test_formats_extra_fields(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        record.custom_field = "custom_value"
        record.request_id = "req-123"
        
        log_record = {}
        formatter.add_fields(log_record, record, {})
        
        assert log_record["custom_field"] == "custom_value"
        assert log_record["request_id"] == "req-123"


class TestLoggingContext:
    """Tests for LoggingContext context manager."""
    
    def test_adds_fields_to_log_record(self):
        logger = logging.getLogger("test")
        
        with LoggingContext(request_id="req-123", user_id="user-123") as ctx:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test",
                args=(),
                exc_info=None,
            )
            # The context manager modifies the record factory
            record2 = logging.getLogRecordFactory()(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test",
                args=(),
                exc_info=None,
            )
            assert getattr(record2, "request_id", None) == "req-123"
            assert getattr(record2, "user_id", None) == "user-123"
    
    def test_nested_contexts(self):
        with LoggingContext(request_id="outer"):
            with LoggingContext(user_id="inner"):
                record = logging.getLogRecordFactory()(
                    name="test",
                    level=logging.INFO,
                    pathname="",
                    lineno=0,
                    msg="test",
                    args=(),
                    exc_info=None,
                )
                # Inner context should override
                assert getattr(record, "user_id", None) == "inner"


class TestSetupLogging:
    """Tests for setup_logging function."""
    
    def test_setup_logging_json_format(self):
        logger = setup_logging(
            level="INFO",
            json_format=True,
        )
        assert logger.level == logging.INFO
        # Check that handlers have JSON formatter
        for handler in logging.getLogger().handlers:
            assert isinstance(handler.formatter, JSONFormatter)
    
    def test_setup_logging_human_format(self):
        logger = setup_logging(
            level="DEBUG",
            json_format=False,
        )
        assert logger.level == logging.DEBUG
        for handler in logging.getLogger().handlers:
            assert isinstance(handler.formatter, logging.Formatter)
            assert not isinstance(handler.formatter, JSONFormatter)
    
    def test_setup_logging_with_file(self):
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            logger = setup_logging(
                level="INFO",
                json_format=True,
                output_file=tmp_path,
            )
            
            # Check that file handler was added
            root_logger = logging.getLogger()
            file_handlers = [h for h in root_logger.handlers if hasattr(h, 'baseFilename')]
            assert len(file_handlers) == 1
            
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def test_log_levels(self):
        logger = setup_logging(level="DEBUG")
        assert logger.level == logging.DEBUG
        
        logger = setup_logging(level="WARNING")
        assert logger.level == logging.WARNING
    
    def test_silences_noisy_loggers(self):
        setup_logging(level="INFO")
        
        # These loggers should be silenced
        assert logging.getLogger("uvicorn.access").level == logging.WARNING
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("groq").level == logging.WARNING


class TestGetLogger:
    """Tests for get_logger function."""
    
    def test_get_logger_returns_logger(self):
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"


class TestLogExecutionTime:
    """Tests for log_execution_time decorator."""
    
    @pytest.mark.asyncio
    async def test_async_function(self):
        logger = logging.getLogger("test")
        with patch.object(logger, 'info') as mock_info:
            @log_execution_time(logger, "test_operation")
            async def async_func():
                await asyncio.sleep(0.01)
                return "result"
            
            result = await async_func()
            assert result == "result"
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert "test_operation" in str(call_args)
            assert "duration_ms" in str(call_args)
    
    def test_sync_function(self):
        logger = logging.getLogger("test")
        with patch.object(logger, 'info') as mock_info:
            @log_execution_time(logger, "sync_operation")
            def sync_func():
                time.sleep(0.01)
                return "sync_result"
            
            result = sync_func()
            assert result == "sync_result"
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert "sync_operation" in str(call_args)
            assert "duration_ms" in str(call_args)
    
    def test_exception_logging(self):
        logger = logging.getLogger("test")
        with patch.object(logger, 'error') as mock_error:
            @log_execution_time(logger, "failing_operation")
            def failing_func():
                raise ValueError("Test error")
            
            with pytest.raises(ValueError):
                failing_func()
            
            mock_error.assert_called_once()
            call_args = mock_error.call_args
            assert "failing_operation failed" in str(call_args)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])