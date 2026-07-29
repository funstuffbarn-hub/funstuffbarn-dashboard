"""
Structured logging configuration with correlation IDs.
"""
import asyncio
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from functools import wraps
from typing import Any

from pythonjsonlogger import jsonlogger

# Context variable for correlation ID
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str:
    """Get current correlation ID or generate new one."""
    cid = correlation_id_var.get()
    if cid is None:
        cid = str(uuid.uuid4())
        correlation_id_var.set(cid)
    return cid


def set_correlation_id(cid: str | None = None) -> str:
    """Set correlation ID for current context."""
    if cid is None:
        cid = str(uuid.uuid4())
    correlation_id_var.set(cid)
    return cid


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True


class JSONFormatter(jsonlogger.JsonFormatter):
    """JSON log formatter with standard fields."""

    def add_fields(self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)

        # Standard fields
        log_record["timestamp"] = datetime.utcnow().isoformat() + "Z"
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["module"] = record.module
        log_record["function"] = record.funcName
        log_record["line"] = record.lineno
        log_record["message"] = record.getMessage()

        # Correlation ID
        log_record["correlation_id"] = get_correlation_id()

        # Exception info
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Extra fields from record
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "name", "pathname", "process", "processName",
                "relativeCreated", "thread", "threadName", "exc_info",
                "exc_text", "stack_info", "correlation_id"
            ]:
                log_record[key] = value


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
    output_file: str | None = None,
) -> logging.Logger:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON format for logs
        output_file: Optional file path for log output
    """
    # Clear existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Set level
    root_logger.setLevel(getattr(logging, level.upper()))

    # Create formatter
    if json_format:
        formatter = JSONFormatter(
            fmt="%(timestamp)s %(level)s %(name)s %(message)s",
            json_ensure_ascii=False,
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(correlation_id)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(CorrelationIdFilter())
    root_logger.addHandler(console_handler)

    # File handler if specified
    if output_file:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            output_file,
            maxBytes=10_000_000,  # 10MB
            backupCount=10,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(CorrelationIdFilter())
        root_logger.addHandler(file_handler)

    # Silence noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("groq").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpcore.connection").setLevel(logging.WARNING)
    logging.getLogger("httpcore.http11").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logger = logging.getLogger()
    logger.info("Logging configured", extra={"json_format": json_format})

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get logger with correlation ID context."""
    return logging.getLogger(name)


class LoggingContext:
    """Context manager for adding extra fields to logs."""

    def __init__(self, **fields):
        self.fields = fields
        self.old_factory = None

    def __enter__(self):
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            for key, value in self.fields.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        self.old_factory = old_factory

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.old_factory:
            logging.setLogRecordFactory(self.old_factory)


def log_execution_time(logger: logging.Logger, operation: str):
    """Decorator to log function execution time."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration = time.perf_counter() - start
                logger.info(
                    f"{operation} completed",
                    extra={"operation": operation, "duration_ms": round(duration * 1000, 2)}
                )
                return result
            except Exception as e:
                duration = time.perf_counter() - start
                logger.error(
                    f"{operation} failed",
                    extra={"operation": operation, "duration_ms": round(duration * 1000, 2), "error": str(e)},
                    exc_info=True
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = time.perf_counter() - start
                logger.info(
                    f"{operation} completed",
                    extra={"operation": operation, "duration_ms": round(duration * 1000, 2)}
                )
                return result
            except Exception as e:
                duration = time.perf_counter() - start
                logger.error(
                    f"{operation} failed",
                    extra={"operation": operation, "duration_ms": round(duration * 1000, 2), "error": str(e)},
                    exc_info=True
                )
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator
