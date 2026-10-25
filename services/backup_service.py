"""
GV Powers ERP - Backup Service
PostgreSQL backup with daily/weekly/monthly retention.
"""

import os
import subprocess
import shutil
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class BackupService:
    """Handles PostgreSQL backup, restore, and retention."""

    def __init__(self, backup_dir: str, database_url: str):
        self.backup_dir = backup_dir
        self.database_url = database_url
        os.makedirs(backup_dir, exist_ok=True)

    def create_backup(self, label: str = "") -> Dict:
        """Create a PostgreSQL backup using pg_dump."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{label}" if label else ""
        filename = f"backup_{timestamp}{suffix}.sql"
        filepath = os.path.join(self.backup_dir, filename)

        try:
            result = subprocess.run(
                ["pg_dump", self.database_url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300,
            )
            if result.returncode != 0:
                return {"success": False, "error": result.stderr.decode()}

            with open(filepath, "wb") as f:
                f.write(result.stdout)

            size = os.path.getsize(filepath)
            return {
                "success": True,
                "filename": filename,
                "filepath": filepath,
                "size": size,
                "date": datetime.now(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def restore_backup(self, filename: str) -> Dict:
        """Restore a PostgreSQL backup using psql."""
        filepath = os.path.join(self.backup_dir, os.path.basename(filename))
        if not os.path.exists(filepath):
            return {"success": False, "error": "Backup file not found"}

        try:
            result = subprocess.run(
                ["psql", self.database_url, "-f", filepath],
                capture_output=True,
                timeout=300,
            )
            if result.returncode != 0:
                return {"success": False, "error": result.stderr.decode()}
            return {"success": True, "message": f"Restored from {filename}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_backups(self) -> List[Dict]:
        """List all backup files sorted by date (newest first)."""
        backups = []
        if not os.path.exists(self.backup_dir):
            return backups
        for f in sorted(os.listdir(self.backup_dir), reverse=True):
            path = os.path.join(self.backup_dir, f)
            if os.path.isfile(path):
                backups.append({
                    "name": f,
                    "size": os.path.getsize(path),
                    "date": datetime.fromtimestamp(os.path.getmtime(path)),
                })
        return backups

    def cleanup_old_backups(self, keep_days: int = 90):
        """Remove backups older than keep_days."""
        cutoff = datetime.now() - timedelta(days=keep_days)
        removed = 0
        for f in os.listdir(self.backup_dir):
            path = os.path.join(self.backup_dir, f)
            if os.path.isfile(path):
                mtime = datetime.fromtimestamp(os.path.getmtime(path))
                if mtime < cutoff:
                    os.remove(path)
                    removed += 1
        return removed

    def get_backup_type(self, filename: str) -> str:
        """Determine backup age category based on filename timestamp."""
        try:
            parts = filename.replace("backup_", "").split("_")
            date_str = parts[0]
            backup_date = datetime.strptime(date_str, "%Y%m%d")
            days_old = (datetime.now() - backup_date).days
            if days_old <= 1:
                return "daily"
            elif days_old <= 7:
                return "weekly"
            elif days_old <= 30:
                return "monthly"
            else:
                return "archive"
        except (ValueError, IndexError):
            return "unknown"
