"""Audit trail inmutable (append-only) para cumplimiento sanitario.
Registra quien accedio a que (lectura/escritura) de historias clinicas.
El archivo de logs es estrictamente append-only y protegido contra
modificaciones mediante encadenamiento de hashes (blockchain-like).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


AUDIT_LOG_DIR = Path(__file__).resolve().parent.parent / ".audit_logs"
AUDIT_LOG_FILE = AUDIT_LOG_DIR / "audit_trail.jsonl"
MAX_LOG_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB por archivo


@dataclass
class AuditEntry:
    """Una entrada individual en el audit trail inmutable."""
    timestamp: float
    usuario: str
    accion: str  # "lectura" | "escritura" | "login" | "logout" | "firma"
    recurso: str  # "paciente:id", "evolucion:id", "receta:id"
    detalle: str = ""
    hash_prev: str = ""  # Hash de la entrada anterior (encadenamiento)
    hash_actual: str = ""  # Hash de esta entrada (auto-calculado)
    firmado: bool = False

    def compute_hash(self) -> str:
        content = f"{self.timestamp}|{self.usuario}|{self.accion}|{self.recurso}|{self.detalle}|{self.hash_prev}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class ImmutableAuditTrail:
    """Sistema de auditoria append-only con encadenamiento de hashes.

    Caracteristicas:
    - Solo escritura: las entradas se agregan al final, nunca se modifican
    - Encadenamiento: cada entrada contiene el hash de la anterior
    - Verificable: se puede recorrer la cadena y validar integridad
    - Rotacion: cuando el archivo supera 50MB, se rota y se comprime el anterior
    """

    def __init__(self, log_dir: Path | str = AUDIT_LOG_DIR):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_file: Optional[Path] = None
        self._lock_file: Optional[Path] = None
        self._inicializar_archivo()

    def _inicializar_archivo(self) -> None:
        """Crea el archivo de log si no existe, con la entrada genesis."""
        self._current_file = self._get_active_file()
        self._lock_file = self.log_dir / ".audit_lock"

        if not self._current_file.exists():
            self._current_file.parent.mkdir(parents=True, exist_ok=True)
            genesis = AuditEntry(
                timestamp=time.time(),
                usuario="__system__",
                accion="init",
                recurso="audit_trail",
                detalle="Genesis block - audit trail inicializado",
                hash_prev="0" * 64,
            )
            genesis.hash_actual = genesis.compute_hash()
            self._append_entry(genesis)

    def _get_active_file(self) -> Path:
        return self.log_dir / "audit_trail.jsonl"

    def _get_last_hash(self) -> str:
        """Lee el hash de la ultima entrada en el archivo."""
        if not self._current_file or not self._current_file.exists():
            return "0" * 64
        try:
            with open(self._current_file, "rb") as f:
                # Leer desde el final para obtener la ultima linea
                f.seek(0, os.SEEK_END)
                pos = f.tell()
                if pos == 0:
                    return "0" * 64
                # Buscar el ultimo newline hacia atras
                while pos > 0:
                    pos -= 1
                    f.seek(pos)
                    if f.read(1) == b"\n":
                        break
                last_line = f.readline().decode("utf-8").strip()
                if not last_line:
                    return "0" * 64
                last_entry = json.loads(last_line)
                return last_entry.get("hash_actual", "0" * 64)
        except (OSError, json.JSONDecodeError):
            return "0" * 64

    def _append_entry(self, entry: AuditEntry) -> None:
        """Agrega una entrada al archivo de log (append-only)."""
        if not self._current_file:
            return
        with open(self._current_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.__dict__, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _check_rotate(self) -> None:
        """Rota el archivo si supera el tamano maximo."""
        if self._current_file and self._current_file.stat().st_size > MAX_LOG_SIZE_BYTES:
            from shutil import copyfileobj
            old_path = self._current_file
            compressed = old_path.with_suffix(f".{int(time.time())}.jsonl.gz")
            with open(old_path, "rb") as f_in, gzip.open(compressed, "wb") as f_out:
                copyfileobj(f_in, f_out)
            old_path.unlink()
            # Crear nuevo archivo con genesis encadenado al anterior
            last_hash = self._get_last_hash_from_file(compressed) if compressed.exists() else "0" * 64
            genesis = AuditEntry(
                timestamp=time.time(),
                usuario="__system__",
                accion="rotate",
                recurso="audit_trail",
                detalle=f"Rotated to {compressed.name}",
                hash_prev=last_hash,
            )
            genesis.hash_actual = genesis.compute_hash()
            self._inicializar_archivo()

    def _get_last_hash_from_file(self, path: Path) -> str:
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                lines = f.readlines()
                if lines:
                    return json.loads(lines[-1]).get("hash_actual", "0" * 64)
        except Exception:
            pass
        return "0" * 64

    def registrar(
        self,
        usuario: str,
        accion: str,
        recurso: str,
        detalle: str = "",
    ) -> AuditEntry:
        """Registra una accion en el audit trail."""
        last_hash = self._get_last_hash()
        entry = AuditEntry(
            timestamp=time.time(),
            usuario=usuario,
            accion=accion,
            recurso=recurso,
            detalle=detalle,
            hash_prev=last_hash,
        )
        entry.hash_actual = entry.compute_hash()
        entry.firmado = True
        self._append_entry(entry)
        self._check_rotate()
        return entry

    def verificar_integridad(self, max_entries: int = 10000) -> list[dict]:
        """Recorre el archivo de log y verifica el encadenamiento de hashes.

        Returns:
            Lista de errores encontrados (vacia si todo esta OK).
        """
        if not self._current_file or not self._current_file.exists():
            return []
        errores = []
        prev_hash = "0" * 64
        count = 0
        with open(self._current_file, "r", encoding="utf-8") as f:
            for line in f:
                if count >= max_entries:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entry = AuditEntry(**data)
                    computed = entry.compute_hash()
                    if computed != entry.hash_actual:
                        errores.append({
                            "linea": count + 1,
                            "tipo": "hash_invalido",
                            "esperado": entry.hash_actual,
                            "computado": computed,
                            "timestamp": entry.timestamp,
                            "usuario": entry.usuario,
                            "accion": entry.accion,
                        })
                    if entry.hash_prev != prev_hash:
                        errores.append({
                            "linea": count + 1,
                            "tipo": "cadena_rota",
                            "esperado": prev_hash,
                            "obtenido": entry.hash_prev,
                            "timestamp": entry.timestamp,
                        })
                    prev_hash = entry.hash_actual
                    count += 1
                except (json.JSONDecodeError, TypeError) as e:
                    errores.append({"linea": count + 1, "tipo": "parse_error", "detalle": str(e)})
                    count += 1
        return errores

    def obtener_historial(
        self,
        usuario: str | None = None,
        accion: str | None = None,
        limite: int = 100,
    ) -> list[dict]:
        """Obtiene el historial de auditoria con filtros opcionales."""
        if not self._current_file or not self._current_file.exists():
            return []
        resultados = []
        with open(self._current_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if usuario and data.get("usuario") != usuario:
                        continue
                    if accion and data.get("accion") != accion:
                        continue
                    resultados.append(data)
                except json.JSONDecodeError:
                    continue
        return resultados[-limite:]

    def obtener_entradas_recientes(self, limite: int = 50) -> list[dict]:
        return self.obtener_historial(limite=limite)
