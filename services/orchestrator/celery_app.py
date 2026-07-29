"""
Celery app configuration for FunStuffBarn orchestrator.
"""
import os

from celery import Celery
from celery.schedules import crontab

from services.shared.config import get_settings

settings = get_settings()

# Create Celery app
app = Celery("funstuffbarn_orchestrator")

# Configuration
app.conf.update(
    # Broker
    broker_url=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    result_backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),

    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task routing
    task_routes={
        "services.agents.mercado.*": {"queue": "mercado"},
        "services.agents.creativo.*": {"queue": "creativo"},
        "services.agents.pinterest.*": {"queue": "pinterest"},
        "services.agents.tienda.*": {"queue": "tienda"},
        "services.agents.estrategia.*": {"queue": "estrategia"},
        "services.orchestrator.backup.*": {"queue": "maintenance"},
        "services.orchestrator.retention.*": {"queue": "maintenance"},
    },

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    worker_disable_rate_limits=False,

    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,

    # Result backend
    result_expires=3600,
    result_extended=True,

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,

    # Beat schedule (periodic tasks)
    beat_schedule={
        # Daily backup at 02:00
        "daily-backup": {
            "task": "services.orchestrator.backup.run_backup_job",
            "schedule": crontab(hour=2, minute=0),
            "options": {"queue": "maintenance"},
        },

        # Daily retention cleanup at 03:00
        "daily-retention-cleanup": {
            "task": "services.orchestrator.retention.apply_retention_policy",
            "schedule": crontab(hour=3, minute=0),
            "options": {"queue": "maintenance"},
        },

        # Daily cycle at 08:00
        "daily-cycle": {
            "task": "services.orchestrator.cycle.run_daily_cycle",
            "schedule": crontab(hour=8, minute=0),
            "options": {"queue": "orchestrator"},
        },

        # Weekly cleanup (Sunday 04:00)
        "weekly-cleanup": {
            "task": "services.orchestrator.backup.cleanup_old_backups",
            "schedule": crontab(day_of_week=0, hour=4, minute=0),
            "options": {"queue": "maintenance"},
        },

        # Health check every 5 minutes
        "health-check": {
            "task": "services.orchestrator.monitoring.health_check",
            "schedule": 300.0,  # Every 5 minutes
            "options": {"queue": "monitoring"},
        },

        # Metrics collection every minute
        "collect-metrics": {
            "task": "services.orchestrator.monitoring.collect_metrics",
            "schedule": 60.0,
            "options": {"queue": "monitoring"},
        },
    },

    # Task default queue
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",

    # Security
    worker_hijack_root_logger=False,
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",

    # Import tasks
    imports=(
        "services.agents.mercado.tasks",
        "services.agents.creativo.tasks",
        "services.agents.pinterest.tasks",
        "services.agents.tienda.tasks",
        "services.agents.estrategia.tasks",
        "services.orchestrator.backup.tasks",
        "services.orchestrator.retention.tasks",
        "services.orchestrator.cycle.tasks",
        "services.orchestrator.monitoring.tasks",
    ),
)

# Auto-discover tasks
app.autodiscover_tasks([
    "services.agents.mercado",
    "services.agents.creativo",
    "services.agents.pinterest",
    "services.agents.tienda",
    "services.agents.estrategia",
    "services.orchestrator.backup",
    "services.orchestrator.retention",
    "services.orchestrator.cycle",
    "services.orchestrator.monitoring",
])

# Task annotations for rate limiting
app.conf.task_annotations = {
    "services.agents.mercado.tasks.*": {"rate_limit": "10/m"},
    "services.agents.creativo.tasks.*": {"rate_limit": "5/m"},
    "services.agents.pinterest.tasks.*": {"rate_limit": "5/m"},
    "services.agents.tienda.tasks.*": {"rate_limit": "10/m"},
    "services.agents.estrategia.tasks.*": {"rate_limit": "5/m"},
}

# Worker initialization
@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Additional periodic tasks setup."""
    pass


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing."""
    print(f"Request: {self.request!r}")


if __name__ == "__main__":
    app.start()
