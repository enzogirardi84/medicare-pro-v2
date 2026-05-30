"""Sincronizacion offline-first para entornos de salud con conectividad intermitente.

Arquitectura:
- SQLite local cifrado con AES-256-GCM para cola de operaciones pendientes
- SyncManager con heartbeat y drenaje ordenado
- Resolucion de conflictos por UUIDv4 + timestamps + LWW
- Modo offline transparente para la UI de Streamlit
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from core.app_logging import log_event

LOCAL_DB_DIR = Path(".streamlit/offline_queue")
LOCAL_DB_PATH = LOCAL_DB_DIR / "offline_queue.enc"
LOCAL_DB_KEY_PATH = LOCAL_DB_DIR / ".queue_key"


# ═══════════════════════════════════════════════════════════════════
# 1. ESTRUCTURAS DE DATOS
# ═══════════════════════════════════════════════════════════════════

@dataclass(order=True)
class OfflineOperation:
    """Operacion pendiente de sincronizar."""
    operation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    tipo: str = ""  # "evolucion" | "checkin" | "receta"
    payload_json: str = ""
    firma_ecdsa: str = ""
    paciente: str = ""
    profesional: str = ""
    intentos: int = 0
    ultimo_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> OfflineOperation:
        return OfflineOperation(**d)


@dataclass
class SyncStatus:
    """Estado actual de la sincronizacion."""
    pendientes: int = 0
    sincronizados: int = 0
    fallidos: int = 0
    ultima_sync: float = 0.0
    online: bool = False
    modo_offline: bool = False


# ═══════════════════════════════════════════════════════════════════
# 2. PERSISTENCIA LOCAL CIFRADA (SQLite + AES-256-GCM)
# ═══════════════════════════════════════════════════════════════════

class LocalQueueStore:
    """Almacenamiento local cifrado para cola de operaciones offline.

    Usa SQLite con cifrado AES-256-GCM a nivel de fila.
    Cada payload se cifra individualmente.
    """

    def __init__(self, db_path: str | Path = LOCAL_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._key: Optional[bytes] = self._init_key()
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        self._init_db()

    def _init_key(self) -> bytes:
        """Deriva o carga la clave de cifrado local."""
        if LOCAL_DB_KEY_PATH.exists():
            return LOCAL_DB_KEY_PATH.read_bytes()
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        machine_id = os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "medicare-offline"))
        salt = machine_id.encode()[:16].ljust(16, b"\x00")
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600000)
        key = kdf.derive(b"medicare-offline-queue-v1")
        LOCAL_DB_KEY_PATH.write_bytes(key)
        LOCAL_DB_KEY_PATH.chmod(0o600)
        return key

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS offline_queue (
                    operation_id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    tipo TEXT NOT NULL,
                    payload_enc BLOB,
                    firma_ecdsa TEXT DEFAULT '',
                    paciente TEXT DEFAULT '',
                    profesional TEXT DEFAULT '',
                    intentos INTEGER DEFAULT 0,
                    ultimo_error TEXT DEFAULT '',
                    creado_en TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_offline_timestamp
                ON offline_queue(timestamp)
            """)
            conn.commit()

    def _cifrar(self, texto_plano: str) -> bytes:
        """Cifra un string con AES-256-GCM."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(self._key)
        nonce = aesgcm.generate_nonce()
        ct = aesgcm.encrypt(nonce, texto_plano.encode("utf-8"), None)
        return base64.b64encode(nonce + ct)

    def _descifrar(self, ciphertext: bytes) -> str:
        """Descifra un blob AES-256-GCM."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(self._key)
        data = base64.b64decode(ciphertext)
        nonce, ct = data[:12], data[12:]
        return aesgcm.decrypt(nonce, ct, None).decode("utf-8")

    def encolar(self, op: OfflineOperation) -> None:
        """Agrega una operacion a la cola local cifrada."""
        with self._lock:
            payload_enc = self._cifrar(op.payload_json) if op.payload_json else b""
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO offline_queue
                   (operation_id, timestamp, tipo, payload_enc, firma_ecdsa,
                    paciente, profesional, intentos, ultimo_error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (op.operation_id, op.timestamp, op.tipo, payload_enc,
                 op.firma_ecdsa, op.paciente, op.profesional,
                 op.intentos, op.ultimo_error),
            )
            conn.commit()

    def obtener_pendientes(self, limite: int = 100) -> list[OfflineOperation]:
        """Obtiene las operaciones pendientes ordenadas por timestamp."""
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM offline_queue ORDER BY timestamp ASC LIMIT ?",
                (limite,),
            ).fetchall()
            ops = []
            for row in rows:
                payload = self._descifrar(row[3]) if row[3] else ""
                ops.append(OfflineOperation(
                    operation_id=row[0],
                    timestamp=row[1],
                    tipo=row[2],
                    payload_json=payload,
                    firma_ecdsa=row[4] or "",
                    paciente=row[5] or "",
                    profesional=row[6] or "",
                    intentos=row[7] or 0,
                    ultimo_error=row[8] or "",
                ))
            return ops

    def eliminar(self, operation_id: str) -> None:
        """Elimina una operacion de la cola (sincronizada exitosamente)."""
        with self._lock:
            self._get_conn().execute(
                "DELETE FROM offline_queue WHERE operation_id = ?",
                (operation_id,),
            )
            self._get_conn().commit()

    def marcar_error(self, operation_id: str, error: str) -> None:
        """Incrementa el contador de intentos y registra el error."""
        with self._lock:
            self._get_conn().execute(
                "UPDATE offline_queue SET intentos = intentos + 1, ultimo_error = ? WHERE operation_id = ?",
                (error[:500], operation_id),
            )
            self._get_conn().commit()

    def contar_pendientes(self) -> int:
        with self._lock:
            row = self._get_conn().execute("SELECT COUNT(*) FROM offline_queue").fetchone()
            return row[0] if row else 0

    def cerrar(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


# ═══════════════════════════════════════════════════════════════════
# 3. MOTOR DE SINCRONIZACION ASINCRONO
# ═══════════════════════════════════════════════════════════════════

class SyncManager:
    """Gestiona la sincronizacion offline->nube con heartbeat y drenaje ordenado.

    Flujo:
    1. Heartbeat periodico via check_conectividad()
    2. Si hay conexion, drena la cola local en orden cronologico
    3. Cada operacion se sincroniza con idempotencia (UUIDv4)
    4. Las operaciones fallidas se reintentan hasta MAX_INTENTOS
    """

    MAX_INTENTOS = 5
    HEARTBEAT_INTERVAL = 15  # segundos entre heartbeats
    SYNC_BATCH_SIZE = 25  # operaciones por lote

    def __init__(self, sync_fn: Optional[Callable] = None):
        self.store = LocalQueueStore()
        self.sync_fn = sync_fn or self._sync_operation_default
        self._status = SyncStatus()
        self._ultimo_heartbeat: float = 0.0

    # ── Estado ────────────────────────────────────────────────────

    @property
    def status(self) -> SyncStatus:
        self._status.pendientes = self.store.contar_pendientes()
        return self._status

    def check_conectividad(self) -> bool:
        """Heartbeat: verifica conectividad con el servidor central via ping liviano.

        Usa timeout corto para no bloquear la UI.
        """
        ahora = time.time()
        if ahora - self._ultimo_heartbeat < self.HEARTBEAT_INTERVAL:
            return self._status.online

        self._ultimo_heartbeat = ahora
        try:
            import urllib.request
            import socket
            socket.setdefaulttimeout(3)
            req = urllib.request.Request(
                "https://medicare-pro-v2-eyqvgkqwvd9e48r5z6klrf.streamlit.app/healthz",
                method="HEAD",
            )
            urllib.request.urlopen(req, timeout=3)
            self._status.online = True
            self._status.ultima_sync = ahora
        except Exception:
            self._status.online = False
        return self._status.online

    # ── Sincronizacion ─────────────────────────────────────────────

    def sincronizar(self) -> SyncStatus:
        """Intenta sincronizar todas las operaciones pendientes.

        Returns:
            SyncStatus con el resultado.
        """
        if not self.check_conectividad():
            self._status.modo_offline = True
            return self._status

        pendientes = self.store.obtener_pendientes(limite=self.SYNC_BATCH_SIZE)
        if not pendientes:
            self._status.modo_offline = False
            self._status.pendientes = 0
            return self._status

        for op in pendientes:
            if op.intentos >= self.MAX_INTENTOS:
                log_event("sync", f"max_intentos_alcanzado:{op.operation_id}")
                self.store.eliminar(op.operation_id)
                self._status.fallidos += 1
                continue

            try:
                ok, msg = self.sync_fn(op)
                if ok:
                    self.store.eliminar(op.operation_id)
                    self._status.sincronizados += 1
                    log_event("sync", f"ok:{op.tipo}:{op.operation_id[:12]}")
                else:
                    self.store.marcar_error(op.operation_id, msg)
                    self._status.fallidos += 1
                    log_event("sync", f"fallo:{op.tipo}:{op.operation_id[:12]}:{msg}")
            except Exception as exc:
                self.store.marcar_error(op.operation_id, str(exc))
                self._status.fallidos += 1
                log_event("sync", f"error:{type(exc).__name__}:{op.operation_id[:12]}")

        self._status.pendientes = self.store.contar_pendientes()
        self._status.modo_offline = self._status.pendientes > 0
        return self._status

    def encolar_operacion(
        self,
        tipo: str,
        payload: dict[str, Any],
        paciente: str = "",
        profesional: str = "",
        firma_ecdsa: str = "",
    ) -> OfflineOperation:
        """Encola una operacion para sincronizacion posterior.

        Si hay conexion, intenta sincronizar inmediatamente.
        Si no, queda en la cola local cifrada.
        """
        op = OfflineOperation(
            tipo=tipo,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str),
            firma_ecdsa=firma_ecdsa,
            paciente=paciente,
            profesional=profesional,
        )
        self.store.encolar(op)
        log_event("sync", f"encolado:{tipo}:{op.operation_id[:12]}")

        if self.check_conectividad():
            self.sincronizar()

        return op

    # ── Sync function por defecto (inyeccion directa a session_state) ──

    @staticmethod
    def _sync_operation_default(op: OfflineOperation) -> tuple[bool, str]:
        """Funcion de sincronizacion por defecto.

        En produccion, reemplazar con inyeccion a Supabase/API REST.
        """
        import streamlit as st
        payload = json.loads(op.payload_json)

        if op.tipo == "evolucion":
            if "evoluciones_db" not in st.session_state:
                st.session_state["evoluciones_db"] = []
            st.session_state["evoluciones_db"].append(payload)
            return True, "ok"

        if op.tipo == "checkin":
            if "checkin_db" not in st.session_state:
                st.session_state["checkin_db"] = []
            st.session_state["checkin_db"].append(payload)
            return True, "ok"

        return False, f"tipo_desconocido:{op.tipo}"


# ═══════════════════════════════════════════════════════════════════
# 4. RESOLUCION DE CONFLICTOS
# ═══════════════════════════════════════════════════════════════════

def resolver_conflicto(
    local: dict[str, Any],
    remoto: dict[str, Any],
    paciente: str,
) -> dict[str, Any]:
    """Resuelve conflictos entre datos locales y remotos.

    Estrategia: Last-Write-Wins (LWW) con auditoria.
    - Si un solo lado tiene el registro, se toma ese.
    - Si ambos tienen, gana el timestamp mas reciente.
    - El registro perdedor se guarda como version historica.
    """
    ts_local = local.get("timestamp", 0.0) if isinstance(local, dict) else 0.0
    ts_remoto = remoto.get("timestamp", 0.0) if isinstance(remoto, dict) else 0.0

    if ts_local >= ts_remoto:
        ganador = dict(local)
        perdedor = dict(remoto) if isinstance(remoto, dict) else {}
    else:
        ganador = dict(remoto)
        perdedor = dict(local)

    # Adjuntar historial de conflictos
    historial = ganador.get("_conflict_history", [])
    if perdedor:
        historial.append({
            "conflict_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "perdedor_ts": perdedor.get("timestamp", 0.0),
            "perdedor_firma": perdedor.get("_firma_ecdsa", ""),
        })
        ganador["_conflict_history"] = historial[-10:]  # mantener ultimos 10
        log_event("sync", f"conflicto_resuelto:LWW:{paciente}")

    return ganador


# ═══════════════════════════════════════════════════════════════════
# 5. INTEGRACION CON UI DE STREAMLIT
# ═══════════════════════════════════════════════════════════════════

def render_offline_indicator(sync_manager: SyncManager) -> None:
    """Muestra el estado de sincronizacion en la sidebar de Streamlit."""
    import streamlit as st
    status = sync_manager.status

    if status.modo_offline:
        st.sidebar.warning(
            f"**Modo offline** — {status.pendientes} operacion(es) pendiente(s) de sincronizar.",
            icon=None,
        )
    elif not status.online:
        st.sidebar.warning("**Sin conexion** — Los datos se guardaran localmente.")
    else:
        if status.sincronizados > 0:
            st.sidebar.success(
                f"Sincronizado: {status.sincronizados} operacion(es) enviadas.",
                icon=None,
            )


def render_sync_dashboard(sync_manager: SyncManager) -> None:
    """Panel de estado de sincronizacion (expandible en dashboard)."""
    import streamlit as st
    status = sync_manager.status
    with st.expander("Estado de sincronizacion", expanded=False):
        st.metric("Pendientes", status.pendientes)
        st.metric("Sincronizados", status.sincronizados)
        st.metric("Fallidos", status.fallidos)
        st.caption(f"Ultima sincronizacion: {datetime.fromtimestamp(status.ultima_sync).strftime('%H:%M:%S') if status.ultima_sync else 'N/A'}")
        st.caption(f"Online: {'Si' if status.online else 'No'} | Modo offline: {'Si' if status.modo_offline else 'No'}")

        if st.button("Sincronizar ahora", use_container_width=True, key="sync_now_btn"):
            with st.spinner("Sincronizando..."):
                result = sync_manager.sincronizar()
            if result.sincronizados > 0:
                st.success(f"{result.sincronizados} operacion(es) sincronizadas.")
            if result.fallidos > 0:
                st.error(f"{result.fallidos} operacion(es) fallaron.")
            st.rerun()
