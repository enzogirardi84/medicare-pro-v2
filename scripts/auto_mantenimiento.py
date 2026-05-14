"""Script de mantenimiento automatico - ejecutar diariamente.
Corre: python scripts/auto_mantenimiento.py
"""
import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKUP_DIR = REPO / "_backups_legacy" / "streamlit"
STREAMLIT_DIR = REPO / ".streamlit"

def limpiar_backups_viejos():
    """Mueve backups de .streamlit/ a _backups_legacy/ si tienen mas de 24hs."""
    print("[mantenimiento] Limpiando backups...")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ahora = datetime.now()
    for f in sorted(STREAMLIT_DIR.glob("backup_*.json")):
        diff = ahora - datetime.fromtimestamp(f.stat().st_mtime)
        if diff > timedelta(hours=24):
            dest = BACKUP_DIR / f.name
            shutil.move(str(f), str(dest))
            print(f"  Movido: {f.name}")
    for f in sorted(STREAMLIT_DIR.glob("strong_recovery_*.json")):
        diff = ahora - datetime.fromtimestamp(f.stat().st_mtime)
        if diff > timedelta(hours=24):
            dest = BACKUP_DIR / f.name
            shutil.move(str(f), str(dest))
            print(f"  Movido: {f.name}")

def limpiar_logs():
    """Limpia archivos de log viejos."""
    print("[mantenimiento] Limpiando logs...")
    for f in REPO.glob("*.log"):
        if f.stat().st_size > 10 * 1024 * 1024:  # >10MB
            f.unlink()
            print(f"  Eliminado: {f.name}")

def verificar_espacio():
    """Verifica espacio en disco."""
    import shutil
    total, used, free = shutil.disk_usage(str(REPO))
    free_gb = free // (2**30)
    print(f"[mantenimiento] Espacio libre: {free_gb} GB")
    if free_gb < 1:
        print("  ALERTA: Espacio de disco bajo!")
    return free_gb > 1

if __name__ == "__main__":
    print(f"Iniciando mantenimiento automatico - {datetime.now().isoformat()}")
    limpiar_backups_viejos()
    limpiar_logs()
    ok = verificar_espacio()
    print(f"Mantenimiento completado. Estado: {'OK' if ok else 'ALERTA'}")
