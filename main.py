"""
Main entry point for FunStuffBarn Agent-Etsy System.
Supports both monolithic and microservices modes.
"""
import os
import sys
import signal
import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from services.shared.config import get_settings
from services.shared.logging import setup_logging, get_logger
from services.shared.celery_app import celery_app
from services.shared.resilience import circuit_breaker_registry

# Import all routes
from services.orchestrator.tasks import (
    run_daily_cycle,
    send_daily_report,
)
from services.orchestrator.monitoring import (
    health_check,
    collect_metrics,
)

settings = get_settings()

# Setup logging
setup_logging(
    level=settings.LOG_LEVEL,
    json_format=settings.LOG_FORMAT == "json",
    output_file=f"{settings.LOGS_DIR}/api.log" if settings.LOGS_DIR else None,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting FunStuffBarn Agent-Etsy System")
    
    # Initialize resources
    # TODO: Initialize Redis, DB connections, etc.
    
    yield
    
    # Cleanup
    logger.info("Shutting down FunStuffBarn Agent-Etsy System")
    # TODO: Close connections


app = FastAPI(
    title="FunStuffBarn Agent-Etsy API",
    description="Automated agent system for Etsy store management",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    from services.orchestrator.monitoring import health_check
    return await health_check()


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from prometheus_client.core import REGISTRY
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


# API routes
@app.post("/api/v1/agents/{agent_type}/run")
async def run_agent(agent_type: str, payload: dict = None, priority: int = 5):
    """Run a specific agent asynchronously."""
    from services.orchestrator.tasks import run_single_agent
    
    task = run_single_agent.delay(agent_type=agent_type, payload=payload, priority=priority)
    
    return {
        "task_id": task.id,
        "agent_type": agent_type,
        "status": "submitted",
    }


@app.post("/api/v1/cycle/run")
async def run_cycle(payload: dict = None):
    """Trigger daily cycle manually."""
    from services.orchestrator.tasks import run_daily_cycle
    
    task = run_daily_cycle.delay(payload=payload)
    
    return {
        "task_id": task.id,
        "status": "submitted",
    }


@app.get("/api/v1/status/{task_id}")
async def get_task_status(task_id: str):
    """Get task status."""
    result = celery_app.AsyncResult(task_id)
    
    return {
        "task_id": task_id,
        "status": result.state,
        "result": result.result if result.ready() else None,
    }


@app.get("/api/v1/agents")
async def list_agents():
    """List all available agents."""
    return {
        "agents": [
            {"type": "mercado", "name": "Market Analysis", "queue": "mercado"},
            {"type": "creativo", "name": "Creative Director", "queue": "creativo"},
            {"type": "pinterest", "name": "Pinterest Trends", "queue": "pinterest"},
            {"type": "tienda", "name": "Store Management", "queue": "tienda"},
            {"type": "estrategia", "name": "Strategy", "queue": "estrategia"},
        ]
    }


@app.get("/api/v1/reports/{report_type}")
async def get_report(report_type: str, date: str = None):
    """Get latest report of a type."""
    from pathlib import Path
    import json
    
    date = date or datetime.utcnow().strftime("%Y-%m-%d")
    report_path = f"/Users/javiermaldonadocorreaair/agente-etsy/reportes/{report_type}_{date}.txt"
    
    path = Path(report_path)
    if not path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": f"Report not found: {report_type} for {date}"}
        )
    
    content = path.read_text(encoding="utf-8")
    return {"report_type": report_type, "date": date, "content": content}


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Mount dashboard (optional - if using separate dashboard)
# app.mount("/dashboard", StaticFiles(directory="dashboard", html=True), name="dashboard")


def main():
    """Main entry point."""
    # Handle signals
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run server
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    main()