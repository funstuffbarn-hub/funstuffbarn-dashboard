#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Market Analysis Agent - Analyzes market trends using Google Trends and Etsy API.
"""
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import uuid4

from services.agents.base import BaseAgent, AgentTask, BaseAgentTask
from services.agents.mercado.agent import MercadoAgent
from services.shared.celery_app import celery_app

logger = logging.getLogger(__name__)


class MercadoTask(BaseAgentTask):
    """Celery task for Market Analysis agent."""
    name = "services.agents.mercado.tasks.run_market_analysis"
    autoretry_for = (ConnectionError, TimeoutError, IOError)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    max_retries = 3


@celery_app.task(bind=True, base=MercadoTask, name="services.agents.mercado.tasks.run_market_analysis")
def run_market_analysis(self, task_data: dict = None) -> dict:
    """
    Run market analysis using Google Trends and Etsy API.
    """
    from uuid import uuid4
    from datetime import datetime
    
    correlation_id = uuid4()
    logger.info(f"Starting market analysis [{correlation_id}]")
    
    started_at = datetime.utcnow()
    
    try:
        # Create agent instance
        agent = MercadoAgent()
        
        # Execute analysis
        result = agent.analyze(
            keywords=task_data.get("keywords") if task_data else None,
            date_range=task_data.get("date_range") if task_data else None,
            geo=task_data.get("geo", "US") if task_data else "US",
        )
        
        # Build report
        report = {
            "date": datetime.utcnow().isoformat(),
            "trends": result.get("trends", []),
            "competition": result.get("competition", []),
            "analysis": result.get("analysis", ""),
            "top_keywords": result.get("keywords", []),
            "price_ranges": result.get("price_ranges", {}),
        }
        
        # Save report
        from services.shared.storage import save_report
        save_report("mercado", report)
        
        return {
            "task_id": str(uuid4()),
            "agent_type": "mercado",
            "status": "completed",
            "result": report,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.exception(f"Market analysis failed: {e}")
        return {
            "task_id": str(uuid4()),
            "agent_type": "mercado",
            "status": "failed",
            "error": str(e),
            "started_at": started_at.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }


def run_market_analysis_async(payload: dict = None, priority: int = 5) -> Any:
    """Run market analysis asynchronously."""
    from services.agents.base import run_agent_task
    return run_agent_task("mercado", payload or {}, priority)


# Export for Celery
__all__ = ["run_market_analysis", "run_market_analysis_async", "MercadoTask"]