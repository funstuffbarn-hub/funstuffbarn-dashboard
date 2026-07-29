"""
Backup job for automated daily backups.
"""
import logging
import os
import shutil
import tarfile
from datetime import datetime
from pathlib import Path

from services.shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def run_backup_job() -> dict:
    """
    Run daily backup job.

    Returns:
        Dictionary with backup results
    """
    logger.info("Starting daily backup job")

    datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(settings.BACKUP_DIR) / f"backup_{datetime.utcnow().strftime('%Y%m%d')}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "backup_dir": str(backup_dir),
        "items": [],
        "errors": [],
    }

    # Define items to backup
    backup_items = [
        ("reportes", Path("/Users/javiermaldonadocorreaair/agente-etsy/reportes")),
        ("prompt_archive", Path("/Users/javiermaldonadocorreaair/agente-etsy/prompt_archive")),
        ("disenos", Path("/Users/javiermaldonadocorreaair/Tienda FunStuffBarn")),
        ("logs", Path("/Users/javiermaldonadocorreaair/agente-etsy/logs")),
        ("config", Path("/Users/javiermaldonadocorreaair/agente-etsy/.env")),
    ]

    for name, source_path in backup_items:
        if not source_path.exists():
            logger.warning(f"Source not found: {source_path}")
            results["errors"].append(f"Source not found: {source_path}")
            continue

        try:
            dest = backup_dir / name
            if dest.exists():
                shutil.rmtree(dest)

            if source_path.is_file():
                shutil.copy2(source_path, dest)
            else:
                shutil.copytree(source_path, dest)

            logger.info(f"Backed up {name} from {source_path}")
            results["items"].append(name)

        except Exception as e:
            logger.error(f"Failed to backup {name}: {e}")
            results["errors"].append(str(e))

    # Create compressed archive
    archive_path = Path(f"{backup_dir}.tar.gz")
    try:
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(backup_dir, arcname=backup_dir.name)

        # Remove uncompressed directory
        shutil.rmtree(backup_dir)

        logger.info(f"Created archive: {archive_path}")
        results["archive"] = str(archive_path)
        results["size_mb"] = round(os.path.getsize(archive_path) / (1024 * 1024), 2)

    except Exception as e:
        logger.error(f"Failed to create archive: {e}")
        results["errors"].append(f"Archive failed: {e}")

    # Cleanup old backups
    cleanup_old_backups()

    logger.info("Backup job completed", extra={"result": results})
    return results


def cleanup_old_backups():
    """Remove old backups based on retention policy."""
    settings = get_settings()
    backup_root = Path(settings.BACKUP_DIR)

    if not backup_root.exists():
        return

    datetime.utcnow()

    for item in sorted(backup_root.iterdir()):
        if not item.is_dir() and not item.suffix == ".tar.gz":
            continue

        try:
            # Parse date from directory name
            name = item.name
            date_str = name.replace("backup_", "").replace(".tar.gz", "")
            item_date = datetime.strptime(date_str, "%Y%m%d")

            age_days = (datetime.utcnow() - item_date).days

            should_delete = False

            # Keep daily for 30 days
            if age_days > 30:
                should_delete = True
            # Keep weekly for 12 weeks (check if it's a Monday)
            elif age_days > 90 and item_date.weekday() != 0:
                should_delete = True
            # Keep monthly for 12 months (keep 1st of month)
            elif age_days > 365 and item_date.day != 1:
                should_delete = True

            if should_delete:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
                logger.info(f"Deleted old backup: {item.name}")

        except ValueError:
            # Not a date-formatted backup
            pass
        except Exception as e:
            logger.error(f"Error cleaning up {item}: {e}")


def list_backups() -> list[dict]:
    """List available backups."""
    settings = get_settings()
    backup_root = Path(settings.BACKUP_DIR)

    if not backup_root.exists():
        return []

    backups = []
    for item in sorted(backup_root.iterdir(), reverse=True):
        if item.suffix == ".gz" or item.is_dir():
            stat = item.stat()
            backups.append({
                "name": item.name,
                "path": str(item),
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

    return backups


def restore_backup(backup_name: str, target_dir: Optional[Path] = None) -> bool:
    """Restore from backup."""
    settings = get_settings()
    backup_root = Path(settings.BACKUP_DIR)
    backup_path = backup_root / backup_name

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_name}")

    target = target_dir or Path("/tmp/restore")
    target.mkdir(parents=True, exist_ok=True)

    if backup_path.suffix == ".gz":
        import tarfile
        with tarfile.open(backup_path, "r:gz") as tar:
            tar.extractall(target)
    else:
        shutil.copytree(backup_path, target / backup_path.name, dirs_exist_ok=True)

    logger.info(f"Restored backup {backup_name} to {target}")
    return True
