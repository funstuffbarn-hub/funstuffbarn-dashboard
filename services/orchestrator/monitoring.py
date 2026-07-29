"""
Monitoring tasks for health checks and metrics collection.
"""
import os
from datetime import datetime
from typing import Any

import psutil
from celery import shared_task
from celery.schedules import crontab

from services.shared.config import get_settings
from services.shared.logging import get_logger
from services.shared.resilience import circuit_breaker_registry

logger = get_logger(__name__)
settings = get_settings()


@shared_task(bind=True, name="services.orchestrator.monitoring.health_check")
def health_check(self) -> dict[str, Any]:
    """
    Comprehensive health check for all system components.
    """
    logger.info("Running health check")

    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "overall": "healthy",
        "checks": {}
    }

    # 1. Disk space
    disk = psutil.disk_usage("/")
    disk_usage = (disk.used / disk.total) * 100
    results["checks"]["disk"] = {
        "status": "healthy" if disk_usage < 90 else "warning" if disk_usage < 95 else "critical",
        "usage_percent": round(disk_usage, 1),
        "free_gb": round(disk.free / (1024**3), 2),
        "total_gb": round(disk.total / (1024**3), 2)
    }
    if disk_usage > 95:
        results["overall"] = "critical"
    elif disk_usage > 90 and results["overall"] == "healthy":
        results["overall"] = "warning"

    # 2. Memory
    memory = psutil.virtual_memory()
    results["checks"]["memory"] = {
        "status": "healthy" if memory.percent < 85 else "warning" if memory.percent < 95 else "critical",
        "usage_percent": memory.percent,
        "available_gb": round(memory.available / (1024**3), 2),
    }
    if memory.percent > 95 and results["overall"] == "healthy":
        results["overall"] = "critical"
    elif memory.percent > 85 and results["overall"] == "healthy":
        results["overall"] = "warning"

    # 3. CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    results["checks"]["cpu"] = {
        "status": "healthy" if cpu_percent < 80 else "warning" if cpu_percent < 95 else "critical",
        "usage_percent": cpu_percent,
    }
    if cpu_percent > 95 and results["overall"] == "healthy":
        results["overall"] = "warning"

    # 4. Redis
    try:
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        r.ping()
        redis_info = r.info()
        results["checks"]["redis"] = {
            "status": "healthy",
            "connected_clients": redis_info.get("connected_clients", 0),
            "used_memory_mb": round(redis_info.get("used_memory", 0) / (1024**2), 2),
        }
    except Exception as e:
        results["checks"]["redis"] = {"status": "critical", "error": str(e)}
        results["overall"] = "critical"

    # 4. Circuit Breakers
    cb_stats = circuit_breaker_registry.get_all_stats()
    cb_healthy = all(v["state"] != "open" for v in cb_stats.values())
    results["checks"]["circuit_breakers"] = {
        "status": "healthy" if cb_healthy else "degraded",
        "breakers": {k: {"state": v["state"], "failures": v["failure_count"]} for k, v in cb_stats.items()},
    }
    if not cb_healthy and results["overall"] == "healthy":
        results["overall"] = "warning"

    # 5. Disk space for data directories
    data_dirs = [
        ("reportes", "/Users/javiermaldonadocorreaair/agente-etsy/reportes"),
        ("prompt_archive", "/Users/javiermaldonadocorreaair/agente-etsy/prompt_archive"),
        ("logs", "/Users/javiermaldonadocorreaair/agente-etsy/logs"),
    ]

    for name, path in data_dirs:
        try:
            usage = psutil.disk_usage(path)
            results["checks"][f"disk_{name}"] = {
                "status": "healthy" if (usage.used / usage.total) < 0.9 else "warning",
                "usage_percent": round((usage.used / usage.total) * 100, 1),
            }
        except Exception as e:
            results["checks"][f"disk_{name}"] = {"status": "error", "error": str(e)}

    logger.info(f"Health check completed: {results['overall']}")
    return results


@shared_task(bind=True, name="services.orchestrator.monitoring.collect_metrics")
def collect_metrics(self) -> dict:
    """
    Collect system metrics for Prometheus/Grafana.
    """
    import os

    import psutil

    metrics = {
        "timestamp": datetime.utcnow().isoformat(),
        "system": {},
        "application": {},
    }

    # System metrics
    psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    metrics["system"] = {
        "cpu_percent": cpu_percent,
        "memory_percent": mem.percent,
        "memory_available_mb": mem.available // (1024**2),
        "disk_percent": (disk.used / disk.total) * 100,
        "disk_free_gb": disk.free // (1024**3),
    }

    # Process metrics
    process = psutil.Process(os.getpid())
    metrics["application"] = {
        "cpu_percent": process.cpu_percent(),
        "memory_mb": process.memory_info().rss // (1024**2),
        "threads": process.num_threads(),
        "open_fds": process.num_fds() if hasattr(process, "num_fds") else 0,
    }

    # Redis metrics
    try:
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        info = r.info()
        metrics["redis"] = {
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_mb": info.get("used_memory", 0) // (1024**2),
            "total_commands": info.get("total_commands_processed", 0),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
        }
    except Exception as e:
        logger.warning(f"Failed to collect Redis metrics: {e}")

    # Celery metrics
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        stats = inspect.stats() or {}
        active = inspect.active() or {}

        total_tasks = sum(len(v) for v in active.values())
        metrics["celery"] = {
            "workers": len(stats),
            "active_tasks": total_tasks,
            "worker_stats": {k: v.get("pool", {}).get("max-concurrency", 0) for k, v in stats.items()}
        }
    except Exception as e:
        logger.warning(f"Failed to collect Celery metrics: {e}")

    logger.info("Metrics collected", extra=metrics)
    return metrics


# Schedule for periodic metrics collection


def get_periodic_schedule():
    """Get periodic metrics collection schedule."""
    return {
        "collect-metrics-every-minute": {
            "task": "services.orchestrator.monitoring.collect_metrics",
            "schedule": 60.0,  # Every minute
        },
        "health-check-every-5-minutes": {
            "task": "services.orchestrator.monitoring.health_check",
            "schedule": crontab(minute="*/5"),
        },
    }
