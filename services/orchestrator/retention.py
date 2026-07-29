"""
Retention policy for reports and data.
"""
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from services.shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def cleanup_old_reports() -> dict:
    """
    Clean up old report files based on retention policy.
    
    Retention policy:
    - Daily reports: keep 30 days
    - Weekly reports (Mondays): keep 12 weeks
    - Monthly reports (1st of month): keep 12 months
    
    Returns:
        Dictionary with cleanup results
    """
    logger.info("Starting retention cleanup")
    
    reportes_dir = Path(settings.REPORTES_DIR) if hasattr(settings, 'REPORTES_DIR') else Path("/Users/javiermaldonadocorreaair/agente-etsy/reportes")
    
    if not reportes_dir.exists():
        logger.warning(f"Reports directory not found: {reportes_dir}")
        return {"cleaned": 0, "errors": ["Directory not found"]}
    
    now = datetime.utcnow()
    deleted = 0
    errors = []
    
    for file_path in sorted(reportes_dir.glob("*.txt")):
        try:
            # Parse date from filename (format: tipo_YYYY-MM-DD.txt)
            name = file_path.stem
            parts = name.split("_")
            if len(parts) < 2:
                continue
            
            date_str = parts[-1]
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            
            age_days = (datetime.utcnow() - file_date).days
            should_delete = False
            
            # Daily: keep 30 days
            if age_days > 30:
                should_delete = True
            # Weekly (Mondays): keep 12 weeks
            elif age_days > 90 and file_date.weekday() != 0:
                should_delete = True
            # Monthly (1st of month): keep 12 months
            elif age_days > 365 and file_date.day != 1:
                should_delete = True
            
            if should_delete:
                file_path.unlink()
                logger.info(f"Deleted old report: {file_path.name}")
                deleted += 1
                
        except Exception as e:
            error_msg = f"Error processing {file_path}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    logger.info(f"Retention cleanup completed: {deleted} files deleted")
    return {
        "deleted": deleted,
        "errors": errors,
        "timestamp": datetime.utcnow().isoformat(),
    }


def cleanup_prompt_archive() -> dict:
    """Clean up old prompt archive entries."""
    logger.info("Starting prompt archive cleanup")
    
    archive_dir = Path("/Users/javiermaldonadocorreaair/agente-etsy/prompt_archive")
    if not archive_dir.exists():
        return {"cleaned": 0, "errors": ["Directory not found"]}
    
    now = datetime.utcnow()
    deleted = 0
    errors = []
    
    for cat_dir in archive_dir.iterdir():
        if not cat_dir.is_dir():
            continue
            
        for subdir in cat_dir.iterdir():
            if not subdir.is_dir():
                continue
                
            for file_path in subdir.glob("*.docx"):
                try:
                    stat = file_path.stat()
                    modified = datetime.fromtimestamp(stat.st_mtime)
                    age_days = (datetime.utcnow() - modified).days
                    
                    # Keep prompts for 1 year
                    if age_days > 365:
                        file_path.unlink()
                        deleted += 1
                        logger.info(f"Deleted old prompt: {file_path}")
                        
                except Exception as e:
                    errors.append(f"Error processing {file_path}: {e}")
    
    return {
        "deleted": deleted,
        "errors": errors,
        "timestamp": datetime.utcnow().isoformat(),
    }


def apply_retention_policy():
    """Apply all retention policies."""
    logger.info("Applying retention policies")
    
    results = {
        "reports": cleanup_old_reports(),
        "prompts": cleanup_prompt_archive(),
    }
    
    total_deleted = results["reports"]["deleted"] + results["prompts"]["deleted"]
    logger.info(f"Retention policies applied: {total_deleted} total files deleted")
    
    return results


if __name__ == "__main__":
    apply_retention_policy()