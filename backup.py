"""Respaldo automático de la base de datos."""
import os
import shutil
from datetime import datetime
from pathlib import Path

from config import BASE_DIR, DATABASE_URL

BACKUP_DIR = BASE_DIR / "backups"
MAX_BACKUPS = 10


def crear_respaldo() -> str | None:
    """Crea un respaldo de la base de datos SQLite."""
    if not DATABASE_URL.startswith("sqlite"):
        return None

    db_path = DATABASE_URL.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        return None

    BACKUP_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"backup_{timestamp}.db"

    shutil.copy2(db_path, backup_path)

    backups = sorted(BACKUP_DIR.glob("backup_*.db"))
    while len(backups) > MAX_BACKUPS:
        backups[0].unlink()
        backups = backups[1:]

    return str(backup_path)


def listar_respaldos() -> list[dict]:
    """Lista los respaldos disponibles."""
    if not BACKUP_DIR.exists():
        return []

    backups = []
    for backup in sorted(BACKUP_DIR.glob("backup_*.db"), reverse=True):
        stat = backup.stat()
        backups.append({
            "nombre": backup.name,
            "fecha": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "tamano": f"{stat.st_size / 1024:.1f} KB",
        })
    return backups
