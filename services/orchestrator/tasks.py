"""
Orchestrator Agent - Coordinates all agents and manages workflows.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import uuid4
from pathlib import Path

from services.shared.config import get_settings
from services.shared.logging import get_logger
from services.shared.celery_app import celery_app
from services.agents.mercado.tasks import run_market_analysis as run_mercado
from services.agents.creativo.tasks import run_creative_ideas as run_creativo
from services.agents.pinterest.tasks import ejecutar as run_pinterest
from services.agents.tienda.tasks import run_tienda
from services.agents.estrategia.tasks import run_estrategia

logger = get_logger(__name__)

settings = get_settings()


class OrchestratorAgent:
    """Coordinates the complete agent workflow."""
    
    def __init__(self):
        self.correlation_id = None
    
    def run_daily_cycle(self, correlation_id: str = None) -> Dict[str, Any]:
        """Execute the complete daily cycle."""
        self.correlation_id = correlation_id or str(uuid4())
        logger.info(f"Starting daily cycle [{self.correlation_id}]")
        
        try:
            # Phase 1: Market analysis and Pinterest trends (parallel)
            logger.info("Phase 1: Market analysis + Pinterest trends")
            mercado_result = run_mercado.delay({}).get(timeout=300)
            pinterest_result = run_pinterest.delay({}).get(timeout=300)
            
            # Phase 2: Creative ideas (depends on Phase 1)
            logger.info("Phase 2: Creative ideas")
            creativo_payload = {
                "market_analysis": mercado_result.get("result", {}),
                "pinterest_trends": pinterest_result.get("result", {}),
            }
            creativo_result = run_creativo.delay(creativo_payload).get(timeout=300)
            
            # Phase 3: Store management + Strategy (parallel)
            logger.info("Phase 3: Store management + Strategy")
            tienda_payload = {
                "creative_ideas": creativo_result.get("result", {}),
                "market_analysis": mercado_result.get("result", {}),
            }
            tienda_task = run_tienda.delay(tienda_payload)
            
            estrategia_payload = {
                "creative_ideas": creativo_result.get("result", {}),
                "market_analysis": mercado_result.get("result", {}),
                "pinterest_trends": pinterest_result.get("result", {}),
            }
            estrategia_task = run_estrategia.delay(estrategia_payload)
            
            # Wait for both
            tienda_result = tienda_task.get(timeout=300)
            estrategia_result = run_estrategia.delay({}).get(timeout=300)
            
            # Phase 4: Send email report
            logger.info("Phase 4: Sending email report")
            send_daily_report.delay({
                "correlation_id": self.correlation_id,
                "mercado": mercado_result,
                "pinterest": pinterest_result,
                "creativo": creativo_result,
                "tienda": tienda_result,
                "estrategia": estrategia_result,
            })
            
            return {
                "status": "completed",
                "correlation_id": self.correlation_id,
                "phases": {
                    "mercado": "completed",
                    "pinterest": "completed",
                    "creativo": "completed",
                    "tienda": "completed",
                    "estrategia": "completed",
                }
            }
            
        except Exception as e:
            logger.exception(f"Daily cycle failed: {e}")
            return {"status": "failed", "error": str(e)}


# Create Celery tasks for each step
from celery import shared_task
from celery import chain, group

@shared_task(bind=True, name="services.orchestrator.tasks.run_daily_cycle")
def run_daily_cycle(self, payload: dict = None) -> dict:
    """Run the complete daily cycle."""
    orchestrator = OrchestratorAgent()
    return orchestrator.run_daily_cycle()


@shared_task(bind=True, name="services.orchestrator.tasks.send_daily_report")
def send_daily_report(self, payload: dict) -> dict:
    """Send daily report via email."""
    from services.orchestrator.email import send_report_email
    
    try:
        html = build_report_html(payload)
        subject = f"FunStuffBarn - Reporte Diario {datetime.utcnow().strftime('%Y-%m-%d')}"
        body = build_report_text(payload)
        
        success = send_report_email(
            to_email=settings.EMAIL_DESTINATION,
            subject=subject,
            body=body,
            html_body=html
        )
        
        return {"success": success, "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.exception(f"Failed to send report: {e}")
        return {"success": False, "error": str(e)}


def build_report_text(payload: dict) -> str:
    """Build plain text report body."""
    parts = [
        f"FunStuffBarn — Reporte Diario {payload.get('date', 'hoy')}",
        "=" * 50,
        "",
        "📊 MERCADO",
        "-" * 30,
        payload.get("mercado", {}).get("result", {}).get("analysis", "Sin datos")[:2000],
        "",
        "📌 PINTEREST",
        "-" * 30,
        payload.get("pinterest", {}).get("result", {}).get("analysis", "Sin datos")[:2000],
        "",
        "🎨 CREATIVO",
        "-" * 30,
        payload.get("creativo", {}).get("result", {}).get("analysis", "Sin datos")[:2000],
        "",
        "🏪 TIENDA",
        "-" * 30,
        payload.get("tienda", {}).get("plan", "")[:2000],
        "",
        "🎯 ESTRATEGIA",
        "-" * 30,
        payload.get("estrategia", {}).get("analysis", "Sin datos")[:2000],
        "",
        "=" * 50,
        f"Generado: {datetime.utcnow().isoformat()}",
    ]
    return "\n".join(parts)


def build_report_html(payload: dict) -> str:
    """Build HTML report body."""
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 800px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2c3e50;">🏪 FunStuffBarn — Reporte Diario</h1>
            <p style="color: #666;">{payload.get('date', 'hoy')}</p>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h2 style="color: #2c3e50;">📊 Mercado</h2>
                <pre style="background: #fff; padding: 15px; border-radius: 4px;">{payload.get('mercado', {{}}).get('result', {{}}).get('analysis', 'Sin datos')[:1500]}</pre>
            </div>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h2 style="color: #2c3e50;">📌 Pinterest Trends</h2>
                <pre style="background: #fff; padding: 15px; border-radius: 4px;">{payload.get('pinterest', {{}}).get('result', {{}}).get('analysis', 'Sin datos')[:1500]}</pre>
            </div>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h2 style="color: #2c3e50;">🎨 Creativo</h2>
                <pre style="background: #fff; padding: 15px; border-radius: 4px;">{payload.get('creativo', {{}}).get('analysis', 'Sin datos')[:1500]}</pre>
            </div>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h2 style="color: #2c3e50;">🏪 Tienda</h2>
                <pre style="background: #fff; padding: 15px; border-radius: 4px;">{payload.get('tienda', {{}}).get('plan', 'Sin datos')[:1500]}</pre>
            </div>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h2 style="color: #2c3e50;">🎯 Estrategia</h2>
                <pre style="background: #fff; padding: 15px; border-radius: 4px;">{payload.get('estrategia', {{}}).get('analysis', 'Sin datos')[:1500]}</pre>
            </div>
            
            <hr style="margin: 30px 0;">
            <p style="color: #999; font-size: 12px;">
                Generado: {datetime.utcnow().isoformat()}<br>
                Correlation ID: {payload.get('correlation_id', 'N/A')}
            </p>
        </div>
    </body>
    </html>
    """


# ============================================================
# Backup & Retention Tasks
# ============================================================

@shared_task(name="services.orchestrator.backup.run_backup")
def run_backup_job() -> dict:
    """Run daily backup of reports, prompts, and configs."""
    import shutil
    import tarfile
    from pathlib import Path
    
    logger.info("Starting backup job...")
    
    backup_root = Path("/Users/javiermaldonadocorreaair/Backups/FunStuffBarn")
    backup_root.mkdir(parents=True, exist_ok=True)
    
    date_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path("/tmp") / f"funstuffbarn_backup_{date_str}"
    backup_dir.mkdir(exist_ok=True)
    
    source_dirs = {
        "reportes": "/Users/javiermaldonadocorreaair/agente-etsy/reportes",
        "prompt_archive": "/Users/javiermaldonadocorreaair/agente-etsy/prompt_archive",
        "config": "/Users/javiermaldonadocorreaair/agente-etsy/.env",
    }
    
    for name, src in source_dirs.items():
        dst = Path(backup_dir) / name
        if Path(src).exists():
            if Path(src).is_file():
                import shutil
                shutil.copy2(src, dst)
            else:
                shutil.copytree(src, dst, dirs_exist_ok=True)
    
    # Create compressed archive
    archive_path = Path(f"/Users/javiermaldonadocorreaair/Backups/FunStuffBarn/backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.tar.gz")
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(backup_dir, arcname=backup_dir.name)
    
    # Cleanup temp
    import shutil
    shutil.rmtree(backup_dir)
    
    logger.info(f"Backup completed: {archive_path}")
    return {"archive": str(archive_path), "size_mb": round(archive_path.stat().st_size / 1024**2, 2)}


@shared_task(name="services.orchestrator.tasks.cleanup_old_reports")
def cleanup_old_reports() -> dict:
    """Apply retention policy to reports."""
    from pathlib import Path
    import os
    
    reportes_dir = Path("/Users/javiermaldonadocorreaair/agente-etsy/reportes")
    if not reportes_dir.exists():
        return {"deleted": 0}
    
    now = datetime.utcnow()
    deleted = 0
    
    for file_path in reportes_dir.glob("*.txt"):
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            age_days = (now - mtime).days
            
            # Keep daily for 30 days, weekly for 12 weeks, monthly for 12 months
            # For simplicity: delete > 30 days
            if age_days > 30:
                file_path.unlink()
                deleted += 1
        except Exception as e:
            logger.warning(f"Error processing {file_path}: {e}")
    
    logger.info(f"Retention cleanup: {deleted} files removed")
    return {"deleted": deleted}


# Export tasks
__all__ = [
    "OrchestratorAgent",
    "run_daily_cycle",
    "send_daily_report",
    "run_backup",
    "cleanup_old_reports",
]