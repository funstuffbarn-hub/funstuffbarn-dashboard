"""
Unit tests for shared/celery_app.py
"""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.shared.celery_app import (
    BaseTask,
    agent_task,
    celery_app,
    create_celery_app,
    run_agent_task,
)


class TestCeleryAppConfig:
    """Tests for Celery app configuration."""

    def test_celery_app_created(self):
        assert celery_app is not None
        assert celery_app.main == "funstuffbarn"

    def test_celery_config_broker(self):
        assert "redis://localhost:6379" in celery_app.conf.broker_url

    def test_celery_config_result_backend(self):
        assert "redis://localhost:6379" in celery_app.conf.result_backend

    def test_task_routes_configured(self):
        routes = celery_app.conf.task_routes
        assert "services.agents.mercado.tasks.*" in routes
        assert "services.agents.creativo.tasks.*" in routes
        assert "services.agents.pinterest.tasks.*" in routes
        assert "services.agents.tienda.tasks.*" in routes
        assert "services.agents.estrategia.tasks.*" in routes

    def test_beat_schedule_configured(self):
        schedule = celery_app.conf.beat_schedule
        assert "daily-cycle" in schedule
        assert "weekly-backup" in schedule
        assert "health-check" in schedule
        assert "retention-cleanup" in schedule

    def test_task_annotations(self):
        annotations = celery_app.conf.task_annotations
        assert "services.agents.mercado.tasks.*" in annotations
        assert annotations["services.agents.mercado.tasks.*"]["rate_limit"] == "10/m"


class TestBaseTask:
    """Tests for BaseTask."""

    def test_autoretry_for(self):
        assert ConnectionError in BaseTask.autoretry_for
        assert TimeoutError in BaseTask.autoretry_for
        assert IOError in BaseTask.autoretry_for

    def test_retry_settings(self):
        assert BaseTask.retry_backoff is True
        assert BaseTask.retry_backoff_max == 600
        assert BaseTask.retry_jitter is True
        assert BaseTask.max_retries == 3
        assert BaseTask.default_retry_delay == 60

    def test_on_failure_logs(self):
        task = BaseTask()
        task.request = Mock(id="task-123")
        exc = ValueError("test error")
        einfo = Mock()

        with patch("services.shared.celery_app.logger.error") as mock_error:
            task.on_failure(exc, "task-123", [], {}, einfo)
            mock_error.assert_called_once()
            call_args = mock_error.call_args
            assert "Task test failed after retries" in str(call_args)

    def test_on_retry_logs(self):
        task = BaseTask()
        task.request = Mock(id="task-123", retries=1)
        exc = ConnectionError("timeout")
        einfo = Mock()

        with patch("services.shared.celery_app.logger.warning") as mock_warning:
            task.on_retry(exc, "task-123", [], {}, einfo)
            mock_warning.assert_called_once()
            call_args = mock_warning.call_args
            assert "retrying" in str(call_args).lower()


class TestRunAgentTask:
    """Tests for run_agent_task function."""

    @pytest.mark.asyncio
    async def test_run_agent_task(self):
        with patch("services.shared.celery_app.celery_app.send_task") as mock_send:
            mock_result = AsyncMock()
            mock_result.id = "test-123"
            mock_result.status = "submitted"
            mock_send.return_value = mock_result

            await run_agent_task("mercado", {"keywords": ["test"]}, priority=5)

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            # call_args is a tuple of (args, kwargs)
            args, kwargs = call_args
            assert args[0] == "services.agents.mercado.tasks.run_mercado"
            # The payload is passed as args=[payload] in kwargs
            assert call_args.kwargs["args"][0] == {"keywords": ["test"]}
            assert call_args.kwargs["priority"] == 5


class TestAgentTaskDecorator:
    """Tests for agent_task decorator."""

    def test_agent_task_decorator(self):
        class TestAgent:
            agent_name = "test_agent"

            def run_sync(self, payload):
                return {"status": "ok"}

        # Test that the decorator can be imported without errors
        assert callable(agent_task)

        # Test that we can create a simple decorated function
        import os
        os.environ["TESTING"] = "1"
        try:
            @agent_task
            class TestAgent:
                agent_name = "test_agent"

                def run_sync(self, payload):
                    return {"status": "ok"}

            assert True  # If we get here, the decorator worked
        finally:
            if "TESTING" in os.environ:
                del os.environ["TESTING"]


class TestCreateCeleryApp:
    """Tests for create_celery_app."""

    def test_creates_celery_app(self):
        app = create_celery_app()
        assert app is not None
        assert app.main == "funstuffbarn"

    def test_app_has_routes(self):
        app = create_celery_app()
        routes = app.conf.task_routes
        assert "services.agents.mercado.tasks.*" in routes
        assert "services.agents.creativo.tasks.*" in routes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
