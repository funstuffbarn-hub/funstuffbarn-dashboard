"""
Base agent class for all agents.
"""
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from celery import Task

from services.shared.config import settings
from services.shared.exceptions import (
    CircuitBreakerOpenError,
)
from services.shared.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryPolicy,
    retry_with_policy,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from agent execution."""
    success: bool
    data: dict | None = None
    error: str | None = None
    duration_seconds: float = 0.0
    metadata: dict = None


class BaseAgent(ABC):
    """Base class for all agents."""

    def __init__(self, agent_name: str, settings: Any | None = None):
        self.agent_name = agent_name
        self.settings = settings
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            base_delay=1.0,
            max_delay=60.0,
        )

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Agent identifier."""
        pass

    @abstractmethod
    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Execute agent logic.

        Args:
            payload: Input payload

        Returns:
            Result dictionary
        """
        pass

    def get_circuit_breaker(self, service: str, config: CircuitBreakerConfig | None = None):
        """Get or create circuit breaker for external service."""
        if service not in self._circuit_breakers:
            self._circuit_breakers[service] = CircuitBreaker(
                name=f"{self.agent_name}:{service}",
                config=config or CircuitBreakerConfig(
                    failure_threshold=5,
                    timeout=60.0,
                )
            )
        return self._circuit_breakers[service]

    async def execute_with_resilience(
        self,
        operation: callable,
        service: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute operation with circuit breaker and retry logic.

        Args:
            operation: Async function to execute
            service: External service name (for circuit breaker)
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Operation result
        """
        cb = self.get_circuit_breaker(service)

        async def _operation():
            return await operation()

        try:
            # Execute through circuit breaker
            result = await cb.call(_operation)
            return result
        except CircuitBreakerOpenError:
            # Try fallback if available
            fallback = getattr(self, f"fallback_{service}", None)
            if fallback:
                logger.warning(f"Circuit breaker open for {service}, using fallback")
                return await fallback()
            raise

    async def execute_with_retry(
        self,
        operation: callable,
        service: str = "internal",
        policy: RetryPolicy | None = None,
    ) -> Any:
        """
        Execute operation with retry logic.

        Args:
            operation: Async function to execute
            service: Service name (for logging)
            policy: Custom retry policy

        Returns:
            Operation result
        """
        return await retry_with_policy(
            operation,
            policy=policy or self._retry_policy,
            on_retry=lambda e, attempt: logger.warning(
                f"{self.agent_name} {service} attempt failed: {e}. "
                f"Retrying... (attempt {attempt})"
            ),
        )

    def _build_celery_task(self) -> Task:
        """Create Celery task for this agent."""
        return CeleryTask(self.agent_name)

    def run_sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Run agent synchronously (for testing/synchronous contexts)."""
        return asyncio.run(self.execute(payload))

    async def run_async(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Run agent asynchronously with full resilience."""
        start_time = time.time()
        correlation_id = uuid4()

        logger.info(
            f"Starting {self.agent_name}",
            extra={
                "agent": self.agent_name,
                "correlation_id": correlation_id,
                "payload_keys": list(payload.keys()) if payload else [],
            }
        )

        try:
            result = await self.execute(payload)
            duration = time.time() - start_time

            logger.info(
                f"{self.agent_name} completed successfully",
                extra={
                    "agent": self.agent_name,
                    "correlation_id": correlation_id,
                    "duration_seconds": duration,
                }
            )

            return {
                "success": True,
                "data": result,
                "duration_seconds": duration,
                "correlation_id": str(correlation_id),
            }

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            logger.error(
                f"{self.agent_name} failed: {error_msg}",
                exc_info=True,
                extra={
                    "agent": self.agent_name,
                    "correlation_id": correlation_id,
                    "duration_seconds": duration,
                }
            )

            return {
                "success": False,
                "error": error_msg,
                "duration_seconds": duration,
                "correlation_id": str(correlation_id),
            }


# ============================================================
# Celery Task Wrapper
# ============================================================

class BaseAgentTask(Task):
    """Base Celery task for agents with error handling."""

    abstract = True
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    max_retries = 3

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(
            f"Task {self.name} failed: {exc}",
            exc_info=True,
            extra={"task_id": task_id, "args": args, "kwargs": kwargs},
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        logger.warning(
            f"Task {self.name} retrying: {exc}",
            extra={"task_id": task_id, "attempt": self.request.retries},
        )
        super().on_retry(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(
            f"Task {self.name} succeeded",
            extra={"task_id": task_id, "duration": self.request.duration},
        )
        super().on_success(retval, task_id, args, kwargs)


class AgentTask(BaseAgentTask):
    """Celery task for an agent."""

    def __init__(self, agent_class):
        self.agent_class = agent_class
        super().__init__()

    def run(self, payload: dict[str, Any], **kwargs) -> dict[str, Any]:
        """Execute agent task."""
        # Create agent instance
        agent = self.agent_class()

        # Run synchronously (Celery runs in worker process)
        import asyncio
        result = asyncio.run(agent.run_async(payload))

        return result


def create_agent_task(agent_class) -> Task:
    """Factory to create Celery task for an agent."""
    task_class = type(
        f"{agent_class.__name__}Task",
        (AgentTask,),
        {"agent_class": agent_class}
    )
    return task_class


# Celery task decorators for easy use
def agent_task(agent_class):
    """Decorator to register agent as Celery task."""
    return create_agent_task(agent_class)


# ============================================================
# Agent Registry
# ============================================================

class AgentRegistry:
    """Registry for managing agents."""

    def __init__(self):
        self._agents: dict[str, Any] = {}
        self._tasks: dict[str, Task] = {}

    def register(self, agent_class):
        """Register an agent class."""
        agent = agent_class()
        self._agents[agent.agent_name] = agent

        # Create Celery task
        task = create_agent_task(agent_class)
        self._tasks[agent.agent_name] = task

        logger.info(f"Registered agent: {agent.agent_name}")

    def get_agent(self, name: str):
        """Get agent by name."""
        return self._agents.get(name)

    def get_task(self, name: str):
        """Get Celery task by name."""
        return self._tasks.get(name)

    def list_agents(self) -> list[str]:
        """List registered agent names."""
        return list(self._agents.keys())

    async def run_agent(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Run agent by name."""
        agent = self._agents.get(name)
        if not agent:
            raise ValueError(f"Agent not found: {name}")
        return await agent.run_async(payload)

    def run_agent_sync(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Run agent synchronously."""
        agent = self._agents.get(name)
        if not agent:
            raise ValueError(f"Agent not found: {name}")
        return agent.run_sync(payload)


# Global registry
agent_registry = AgentRegistry()


# ============================================================
# Celery App Configuration
# ============================================================

def create_celery_app() -> Celery:
    """Create and configure Celery application."""
    from celery import Celery

    app = Celery("funstuffbarn_agents")

    # Load config from settings
    app.conf.update(
        broker_url=settings.celery_broker_url,
        result_backend=settings.celery_result_backend,
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=1800,  # 30 minutes
        task_soft_time_limit=1500,  # 25 minutes
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=100,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        result_expires=86400,  # 24 hours
        task_routes={
            "services.agents.mercado.*": {"queue": "agents"},
            "services.agents.creativo.*": {"queue": "agents"},
            "services.agents.pinterest.*": {"queue": "agents"},
            "services.agents.tienda.*": {"queue": "agents"},
            "services.agents.estrategia.*": {"queue": "agents"},
        },
        beat_schedule={
            "daily-market-analysis": {
                "task": "services.agents.mercado.tasks.run_mercado",
                "schedule": 86400.0,  # Daily
            },
            "daily-creative": {
                "task": "services.agents.creativo.tasks.run_creativo",
                "schedule": 86400.0,
            },
            "daily-pinterest": {
                "task": "services.agents.pinterest.tasks.run_pinterest",
                "schedule": 86400.0,
            },
            "daily-store": {
                "task": "services.agents.tienda.tasks.run_tienda",
                "schedule": 86400.0,
            },
            "daily-strategy": {
                "task": "services.agents.estrategia.tasks.run_estrategia",
                "schedule": 86400.0,
            },
            "weekly-backup": {
                "task": "services.shared.tasks.backup",
                "schedule": 604800.0,  # Weekly
            },
        },
    )

    return app


# Celery app instance
celery_app = create_celery_app()


# ============================================================
# Storage Utilities
# ============================================================

def save_report(report_type: str, report: dict[str, Any]) -> str:
    """Save report to filesystem."""
    import json
    from pathlib import Path

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"{report_type}_{date_str}.json"

    report_dir = Path(__file__).parent.parent.parent / "data" / "reports" / report_type
    report_dir.mkdir(parents=True, exist_ok=True)

    filepath = report_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"Report saved: {filepath}")
    return str(filepath)


def load_latest_report(report_type: str) -> dict | None:
    """Load latest report of given type."""
    import json
    from pathlib import Path

    report_dir = Path(__file__).parent.parent.parent / "data" / "reports" / report_type
    if not report_dir.exists():
        return None

    files = sorted(report_dir.glob("*.json"), reverse=True)
    if not files:
        return None

    with open(files[0], encoding="utf-8") as f:
        return json.load(f)


# Export all
__all__ = [
    "BaseAgent",
    "AgentTask",
    "agent_task",
    "AgentRegistry",
    "agent_registry",
    "celery_app",
    "settings",
    "AgentResult",
    "create_celery_app",
    "save_report",
    "load_latest_report",
]
