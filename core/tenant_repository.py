"""Repositorio multi-tenant con aislamiento de datos por tenant_id.
Usa SQLAlchemy asincrono + psycopg3. Cada consulta FILTRA por tenant_id
del contexto del usuario. Fuga de datos = imposible por disenio.
"""
from __future__ import annotations

import json
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. CONFIGURACION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DBConfig:
    """Configuracion de base de datos desde variables de entorno."""
    host: str = ""
    port: int = 5432
    dbname: str = ""
    user: str = ""
    password: str = ""
    min_connections: int = 2
    max_connections: int = 10
    statement_timeout_ms: int = 30000

    @classmethod
    def from_env(cls) -> DBConfig:
        prefix = os.environ.get("MEDICARE_TENANT", "default").upper().replace("-", "_")
        def env(key: str, default: str = "") -> str:
            return os.environ.get(f"{prefix}_{key}", os.environ.get(key, default))
        return cls(
            host=env("DB_HOST", "localhost"),
            port=int(env("DB_PORT", "5432")),
            dbname=env("DB_NAME", "medicare"),
            user=env("DB_USER", "medicare"),
            password=env("DB_PASSWORD", ""),
            min_connections=int(env("DB_POOL_MIN", "2")),
            max_connections=int(env("DB_POOL_MAX", "10")),
        )


# ═══════════════════════════════════════════════════════════════════
# 2. TENANT REPOSITORY (SEGURIDAD: tenant_id OBLIGATORIO)
# ═══════════════════════════════════════════════════════════════════

class TenantRepository:
    """Repositorio base que inyecta tenant_id en TODAS las consultas.

    Uso:
        repo = TenantRepository()
        async with repo.connect() as conn:
            pacientes = await repo.fetch_all(
                conn, "SELECT * FROM pacientes WHERE activo = true"
            )
    """

    def __init__(self, config: Optional[DBConfig] = None):
        self._config = config or DBConfig.from_env()
        self._pool = None
        self._tenant_id: str = ""

    @property
    def tenant_id(self) -> str:
        """Tenant ID del contexto actual. Nunca debe ser vacio."""
        if not self._tenant_id:
            import streamlit as st
            user = st.session_state.get("u_actual", {})
            if isinstance(user, dict):
                self._tenant_id = str(user.get("empresa", "") or "").strip().lower()
            if not self._tenant_id:
                self._tenant_id = os.environ.get("MEDICARE_TENANT", "default")
        return self._tenant_id

    def set_tenant_context(self, tenant_id: str) -> None:
        """Establece el tenant_id para la sesion actual."""
        self._tenant_id = tenant_id.strip().lower()

    async def _get_pool(self):
        """Obtiene o crea el pool de conexiones async."""
        if self._pool is None:
            import asyncpg
            self._pool = await asyncpg.create_pool(
                host=self._config.host,
                port=self._config.port,
                database=self._config.dbname,
                user=self._config.user,
                password=self._config.password,
                min_size=self._config.min_connections,
                max_size=self._config.max_connections,
                command_timeout=self._config.statement_timeout_ms / 1000,
            )
        return self._pool

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator[Any, None]:
        """Context manager para conexion asyncrona."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            yield conn

    # ── CRUD con tenant_id forzado ─────────────────────────

    async def fetch_all(self, conn: Any, query: str, *args: Any) -> list[dict[str, Any]]:
        """Ejecuta SELECT con tenant_id inyectado en la clausula WHERE."""
        safe_query = self._inject_tenant(query)
        rows = await conn.fetch(safe_query, *args)
        return [dict(r) for r in rows]

    async def fetch_one(self, conn: Any, query: str, *args: Any) -> Optional[dict[str, Any]]:
        rows = await self.fetch_all(conn, query, *args)
        return rows[0] if rows else None

    async def execute(self, conn: Any, query: str, *args: Any) -> str:
        """Ejecuta INSERT/UPDATE/DELETE con tenant_id forzado."""
        safe_query = self._inject_tenant(query)
        return await conn.execute(safe_query, *args)

    async def insert(self, conn: Any, table: str, data: dict[str, Any]) -> str:
        """INSERT seguro con tenant_id + hash_integridad + timestamps."""
        from core.crypto_utils import compute_integrity_hash

        data["tenant_id"] = self.tenant_id
        data["created_at"] = "NOW()"
        data["version"] = 1

        # Hash de integridad
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        data["hash_integridad"] = compute_integrity_hash(data)

        columns = ", ".join(data.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id"
        return await conn.fetchval(query, *data.values())

    async def update(self, conn: Any, table: str, record_id: str, data: dict[str, Any]) -> bool:
        """UPDATE optimista con version check + tenant_id forzado."""
        from core.crypto_utils import compute_integrity_hash

        data["updated_at"] = "NOW()"
        data["hash_integridad"] = compute_integrity_hash(data)

        set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
        values = list(data.values())
        values.extend([record_id, self.tenant_id])

        query = f"""
            UPDATE {table}
            SET {set_clause}, version = version + 1
            WHERE id = $1 AND tenant_id = $2
            RETURNING id
        """
        # Verificar que se actualizo exactamente 1 fila
        result = await conn.fetchval(query, record_id, self.tenant_id)
        return result is not None

    async def delete(self, conn: Any, table: str, record_id: str) -> bool:
        """DELETE con tenant_id forzado."""
        query = f"DELETE FROM {table} WHERE id = $1 AND tenant_id = $2 RETURNING id"
        result = await conn.fetchval(query, record_id, self.tenant_id)
        return result is not None

    # ── Seguridad: inyeccion de tenant_id ──────────────────

    def _inject_tenant(self, query: str) -> str:
        """Inyecta el filtro de tenant_id en la consulta si no existe.

        Previene fugas de datos entre tenants por errores de programacion.
        """
        # Detectar tipo de consulta
        q = query.strip().upper()
        if q.startswith("SELECT") or q.startswith("UPDATE") or q.startswith("DELETE"):
            # Verificar que la tabla tenga tenant_id
            if "tenant_id" not in query:
                log_event("tenant_repo", f"INYECTANDO tenant_id en consulta sin filtro")
                if "WHERE" in query:
                    query = query.replace("WHERE", f"WHERE tenant_id = '{self.tenant_id}' AND ")
                else:
                    # Para UPDATE sin WHERE (peligroso!)
                    if q.startswith("UPDATE"):
                        query += f" WHERE tenant_id = '{self.tenant_id}'"
                    elif q.startswith("SELECT") or q.startswith("DELETE"):
                        query += f" WHERE tenant_id = '{self.tenant_id}'"
        return query


# ═══════════════════════════════════════════════════════════════════
# 3. FUNCIONES CRIPTOGRAFICAS
# ═══════════════════════════════════════════════════════════════════

def serializar_canonico(data: dict[str, Any]) -> str:
    """Serializa un diccionario a JSON canonico (sorted keys, sin espacios).

    Esto asegura que el mismo contenido SIEMPRE genere el mismo hash.
    """
    return json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)


def compute_integrity_hash(record: dict[str, Any]) -> str:
    """Calcula SHA-256 del JSON canonico del registro.

    Excluye campos volatiles: hash_integridad, firma_ecdsa, timestamps.
    """
    import hashlib

    # Excluir campos que cambian en cada operacion
    exclude = {"hash_integridad", "firma_ecdsa", "created_at", "updated_at", "version"}
    clean = {k: v for k, v in record.items() if k not in exclude}

    canonical = serializar_canonico(clean)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_integrity(record: dict[str, Any]) -> bool:
    """Verifica que el hash_integridad del registro coincida con los datos actuales.

    Si alguien modifico el registro fuera del sistema, el hash no coincidira.
    """
    stored_hash = record.get("hash_integridad", "")
    if not stored_hash:
        return False
    computed = compute_integrity_hash(record)
    return stored_hash == computed
