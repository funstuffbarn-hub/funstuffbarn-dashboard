"""
Celery configuration for distributed task processing.
"""
import os
import uuid

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_failure, task_postrun, task_prerun

from .logging import get_correlation_id, get_logger, set_correlation_id

logger = get_logger(__name__)

# Celery app instance
celery_app = Celery(
    "funstuffbarn",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    include=[
        "services.agents.mercado.tasks",
        "services.agents.creativo.tasks",
        "services.agents.pinterest.tasks",
        "services.agents.tienda.tasks",
        "services.agents.estrategia.tasks",
        "services.orchestrator.tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task routing
    task_routes={
        "services.agents.mercado.tasks.*": {"queue": "mercado"},
        "services.agents.creativo.tasks.*": {"queue": "creativo"},
        "services.agents.pinterest.tasks.*": {"queue": "pinterest"},
        "services.agents.tienda.tasks.*": {"queue": "tienda"},
        "services.agents.estrategia.tasks.*": {"queue": "estrategia"},
        "services.orchestrator.tasks.*": {"queue": "orchestrator"},
    },

    # Task annotations for rate limiting
    task_annotations={
        "services.agents.mercado.tasks.*": {"rate_limit": "10/m"},
        "services.agents.creativo.tasks.*": {"rate_limit": "5/m"},
        "services.agents.pinterest.tasks.*": {"rate_limit": "5/m"},
        "services.agents.tienda.tasks.*": {"rate_limit": "10/m"},
        "services.agents.estrategia.tasks.*": {"rate_limit": "5/m"},
    },

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    worker_disable_rate_limits=False,

    # Task settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes

    # Result backend
    result_expires=86400,  # 24 hours
    result_compression="gzip",

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,

    # Beat schedule (periodic tasks)
    beat_schedule={
        "daily-cycle": {
            "task": "services.orchestrator.tasks.run_daily_cycle",
            "schedule": crontab(hour=8, minute=0),  # 8 AM UTC
        },
        "weekly-backup": {
            "task": "services.orchestrator.tasks.run_backup",
            "schedule": crontab(hour=2, minute=0, day_of_week=0),  # Sunday 2 AM
        },
        "health-check": {
            "task": "services.orchestrator.tasks.health_check",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
        },
        "retention-cleanup": {
            "task": "services.orchestrator.tasks.retention_cleanup",
            "schedule": crontab(hour=3, minute=0),  # 3 AM daily
        },
    },

    # Task routing by priority
    task_default_priority=5,
    task_queue_max_priority=10,

    # Dead letter queue
    task_default_retry_delay=60,
    task_max_retries=3,
)

# ============================================================
# Signals for correlation ID propagation
# ============================================================

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kw):
    """Set correlation ID before task execution."""
    # Try to get correlation ID from task headers
    correlation_id = None
    if task.request.headers:
        correlation_id = task.request.headers.get("correlation_id")

    if not correlation_id:
        correlation_id = str(task.request.id)

    set_correlation_id(correlation_id)

    logger.info(
        f"Task started: {task.name}",
        extra={
            "task_id": task_id,
            "task_name": task.name,
            "correlation_id": correlation_id,
        }
    )


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kw):
    """Log task completion."""
    duration = None
    if hasattr(sender, "request") and hasattr(sender.request, "started_at"):
        import time
        duration = time.time() - sender.request.started_at

    logger.info(
        f"Task completed: {sender.name if sender else 'unknown'}",
        extra={
            "task_id": task_id,
            "state": state,
            "duration_seconds": duration,
            "correlation_id": get_correlation_id(),
        }
    )


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kw):
    """Log task failure."""
    logger.error(
        f"Task failed: {sender.name if sender else 'unknown'}",
        extra={
            "task_id": task_id,
            "exception": str(exception),
            "correlation_id": get_correlation_id(),
        },
        exc_info=True
    )


# ============================================================
# Base Task Class with Retry Logic
# ============================================================

class BaseTask:
    """Base task class with built-in retry logic and correlation ID."""

    # Default task name - overridden by @celery_app.task decorator
    name = "test"

    autoretry_for = (
        ConnectionError,
        TimeoutError,
        IOError,
    )
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes
    retry_jitter = True
    max_retries = 3
    default_retry_delay = 60

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Log task failure."""
        logger.error(
            f"Task {self.name} failed after retries",
            extra={
                "task_id": self.request.id,
                "exception": str(exc),
                "correlation_id": get_correlation_id(),
            },
            exc_info=True
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Log task retry."""
        logger.warning(
            f"Task {self.name} retrying",
            extra={
                "task_id": task_id,
                "attempt": self.request.retries + 1,
                "max_retries": self.max_retries,
                "exception": str(exc),
                "correlation_id": get_correlation_id(),
            }
        )


# ============================================================
# Agent Task Decorator
# ============================================================

def agent_task(agent_class):
    """Decorator to register an agent class as a Celery task."""
    task_name = f"services.agents.{agent_class.agent_name}.tasks.run_{agent_class.agent_name}"

    # For testing, return a simple function
    import os
    if os.getenv("TESTING") == "1":
        return lambda payload=None: agent_class().run_sync(payload or {})

    task_name = f"services.agents.{agent_class.agent_name}.tasks.run_{agent_class.agent_name}"
    celery_app.task(
        bind=True,
        base=BaseTask,
        name=f"services.agents.{agent_class.agent_name}.tasks.run_{agent_class.agent_name}"
    )(lambda self, payload=None: agent_class().run_sync(payload or {}))

    return celery_app.tasks.get(task_name)


# ============================================================
# Task Helpers
# ============================================================

async def run_agent_task(
    agent_type: str,
    payload: dict,
    priority: int = 5,
    correlation_id: Optional[str] = None,
) -> Any:
    """
    Run an agent task asynchronously.

    Args:
        agent_type: Type of agent (mercado, creativo, pinterest, tienda, estrategia)
        payload: Input data for the agent
        priority: Task priority (0-10)
        correlation_id: Optional correlation ID

    Returns:
        Task result
    """


    # Send task with correlation ID
    headers = {"correlation_id": correlation_id or str(uuid.uuid4())}

    result = celery_app.send_task(
        f"services.agents.{agent_type}.tasks.run_{agent_type}",
        args=[payload],
        headers=headers,
        priority=priority,
    )

    return result


def create_celery_app() -> Celery:
    """Create and configure Celery app."""
    return celery_app


# For direct imports
__all__ = [
    "celery_app",
    "BaseTask",
    "run_agent_task",
    "get_logger",
    "get_correlation_id",
    "set_correlation_id",
]
