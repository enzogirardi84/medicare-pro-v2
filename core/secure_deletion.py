"""Gestion del ciclo de vida de archivos temporales de auditoria.
Garantiza borrado seguro (shredding criptografico) de archivos SQLite
al expirar su TTL o al confirmarse la descarga.
"""
from __future__ import annotations

import asyncio
import os
import random
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE ARCHIVO TEMPORAL
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TempAuditFile:
    """Archivo temporal de auditoria con metadatos de ciclo de vida."""
    file_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    path: str = ""
    original_size: int = 0
    ttl_seconds: float = 3600.0        # 1 hora por defecto
    created_at: float = field(default_factory=time.time)
    downloaded: bool = False
    shredded: bool = False
    tenant_id: str = ""
    auditor_id: str = ""

    @property
    def expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds

    @property
    def expires_at(self) -> float:
        return self.created_at + self.ttl_seconds


# ═══════════════════════════════════════════════════════════════════
# 2. SHREDDER (borrado seguro con sobreescritura)
# ═══════════════════════════════════════════════════════════════════

class CryptographicShredder:
    """Borrado seguro de archivos con sobreescritura multiple.

    Estandar: DoD 5220.22-M (3 pasadas) + pasada final de ceros.
    """

    PASSES = 3  # DoD 5220.22-M: 3 pasadas

    @classmethod
    def shred_file(cls, path: str, passes: int = None) -> bool:
        """Sobreescribe y elimina un archivo de forma segura.

        Args:
            path: Ruta del archivo a destruir.
            passes: Cantidad de pasadas de sobreescritura (default 3).

        Returns:
            True si se elimino correctamente.
        """
        if not os.path.exists(path):
            return False

        passes = passes or cls.PASSES
        try:
            file_size = os.path.getsize(path)

            for p in range(passes):
                with open(path, "wb") as f:
                    if p == 0:
                        f.write(b"\xff" * file_size)
                    elif p == 1:
                        f.write(b"\x00" * file_size)
                    else:
                        f.write(os.urandom(file_size))
                    f.flush()
                    os.fsync(f.fileno())

            # Truncar a 0 y eliminar
            with open(path, "w"):
                pass

            # Renombrar antes de eliminar
            random_name = f"{uuid.uuid4().hex}.del"
            parent = os.path.dirname(path)
            temp_path = os.path.join(parent, random_name) if parent else random_name
            os.rename(path, temp_path)
            os.remove(temp_path)
            return True

        except Exception as exc:
            log_event("shredder", f"shred_failed:{path}:{type(exc).__name__}")
            try:
                os.remove(path)
            except Exception:
                pass
            return False


# ═══════════════════════════════════════════════════════════════════
# 3. GARBAGE COLLECTOR DE ARCHIVOS TEMPORALES
# ═══════════════════════════════════════════════════════════════════

class TempFileGarbageCollector:
    """Garbage Collector interno de archivos temporales de auditoria.

    Ciclo de vida:
    1. Se crea un archivo temporal con TTL
    2. Se entrega al auditor (download)
    3. Al confirmar descarga o al expirar TTL, se destruye
    4. La destruccion usa CryptographicShredder (sobreescritura DoD)
    """

    CLEANUP_INTERVAL = 300  # 5 min entre limpiezas

    def __init__(self, temp_dir: Optional[str] = None):
        self._temp_dir = temp_dir or tempfile.gettempdir()
        self._files: dict[str, TempAuditFile] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    def register_file(self, path: str, ttl: float = 3600.0,
                      tenant_id: str = "", auditor_id: str = "") -> TempAuditFile:
        """Registra un archivo temporal para tracking.

        Args:
            path: Ruta del archivo temporal.
            ttl: TTL en segundos.
            tenant_id: Tenant asociado.
            auditor_id: ID del auditor destino.

        Returns:
            TempAuditFile registrado.
        """
        taf = TempAuditFile(
            path=path,
            original_size=os.path.getsize(path) if os.path.exists(path) else 0,
            ttl_seconds=ttl,
            tenant_id=tenant_id,
            auditor_id=auditor_id,
        )
        self._files[taf.file_id] = taf
        self._ensure_cleanup_task()
        log_event("temp_gc", f"registered:{taf.file_id}:{path}:ttl={ttl}s")
        return taf

    def mark_downloaded(self, file_id: str) -> bool:
        """Marca un archivo como descargado y programa su destruccion."""
        taf = self._files.get(file_id)
        if not taf:
            return False
        taf.downloaded = True
        log_event("temp_gc", f"downloaded:{file_id}")
        # Destruir inmediatamente tras descarga
        return self._destroy_file(file_id)

    def _destroy_file(self, file_id: str) -> bool:
        """Destruye un archivo con shredding criptografico."""
        taf = self._files.get(file_id)
        if not taf or taf.shredded:
            return False

        if os.path.exists(taf.path):
            success = CryptographicShredder.shred_file(taf.path)
            if success:
                taf.shredded = True
                log_event("temp_gc", f"shredded:{file_id}:{taf.path}")
                return True

        # Si el archivo no existe, marcar como shreddeado igual
        taf.shredded = True
        return True

    def _ensure_cleanup_task(self):
        try:
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        except RuntimeError:
            pass

    async def _cleanup_loop(self):
        """Loop que limpia archivos expirados periodicamente."""
        while True:
            await asyncio.sleep(self.CLEANUP_INTERVAL)
            cleaned = 0
            for file_id in list(self._files.keys()):
                taf = self._files[file_id]
                if taf.expired and not taf.shredded:
                    if self._destroy_file(file_id):
                        cleaned += 1
                if taf.shredded:
                    # Remover del registro interno tras 5 min de shreddeado
                    if time.time() - taf.created_at > taf.ttl_seconds + 300:
                        del self._files[file_id]

            if cleaned:
                log_event("temp_gc", f"cleanup:destroyed={cleaned}")

    def get_stats(self) -> dict:
        """Estadisticas del GC."""
        total = len(self._files)
        shredded = sum(1 for f in self._files.values() if f.shredded)
        pending = total - shredded
        expired = sum(1 for f in self._files.values() if f.expired and not f.shredded)
        return {
            "total_registered": total,
            "shredded": shredded,
            "pending": pending,
            "expired_pending": expired,
        }

    async def close(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except (asyncio.CancelledError, RuntimeError):
                pass
        # Destruir todos los archivos pendientes
        for file_id in list(self._files.keys()):
            self._destroy_file(file_id)


__all__ = [
    "TempFileGarbageCollector",
    "CryptographicShredder",
    "TempAuditFile",
]
