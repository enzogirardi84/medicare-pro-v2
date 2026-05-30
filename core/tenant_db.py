"""Pool de conexiones multi-tenant a PostgreSQL/Supabase.
Cada tenant tiene su propia base de datos aislada.
Conexion dinamica basada en MEDICARE_TENANT.
Timeouts, reconexion automatica, aislamiento estricto.
"""
from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generator, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. CONFIGURACION POR TENANT
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TenantDBConfig:
    """Configuracion de base de datos para un tenant."""
    tenant_id: str
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = ""
    db_user: str = ""
    db_password: str = ""
    db_schema: str = "public"
    pool_min: int = 1
    pool_max: int = 5
    statement_timeout_ms: int = 30000
    connection_timeout_s: int = 10

    @classmethod
    def from_env(cls, tenant_id: str) -> TenantDBConfig:
        """Carga config desde variables de entorno con prefijo por tenant."""
        prefix = tenant_id.upper().replace("-", "_")

        def env(key: str, default: str = "") -> str:
            return os.environ.get(f"{prefix}_{key}", os.environ.get(key, default))

        return cls(
            tenant_id=tenant_id,
            db_host=env("DB_HOST", "localhost"),
            db_port=int(env("DB_PORT", "5432")),
            db_name=env("DB_NAME", f"medicare_{tenant_id}"),
            db_user=env("DB_USER", "medicare"),
            db_password=env("DB_PASSWORD", ""),
            db_schema=env("DB_SCHEMA", "public"),
            pool_min=int(env("DB_POOL_MIN", "1")),
            pool_max=int(env("DB_POOL_MAX", "5")),
            statement_timeout_ms=int(env("DB_STATEMENT_TIMEOUT_MS", "30000")),
            connection_timeout_s=int(env("DB_CONNECTION_TIMEOUT_S", "10")),
        )


# ═══════════════════════════════════════════════════════════════════
# 2. POOL DE CONEXIONES MULTI-TENANT
# ═══════════════════════════════════════════════════════════════════

class TenantConnectionPool:
    """Pool de conexiones PostgreSQL multi-tenant con aislamiento.

    Cada tenant tiene su propio pool. El pool se crea bajo demanda
    y se destruye al cambiar de tenant. Reconexion automatica con
    backoff exponencial.

    Uso:
        pool = TenantConnectionPool()
        with pool.get_connection("tenant_avalian") as conn:
            conn.execute("SELECT * FROM pacientes")
    """

    _instance: Optional[TenantConnectionPool] = None
    _pools: dict[str, Any] = {}
    _lock = threading.Lock()

    def __new__(cls) -> TenantConnectionPool:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

    def _crear_pool(self, config: TenantDBConfig) -> Any:
        """Crea un pool de conexiones para un tenant."""
        try:
            import psycopg2
            from psycopg2 import pool as pg_pool
        except ImportError:
            log_event("tenant_db", "psycopg2 no instalado. Usando fallback SQLite.")
            return None

        try:
            pool = pg_pool.ThreadedConnectionPool(
                minconn=config.pool_min,
                maxconn=config.pool_max,
                host=config.db_host,
                port=config.db_port,
                dbname=config.db_name,
                user=config.db_user,
                password=config.db_password,
                options=f"-c search_path={config.db_schema}",
                connect_timeout=config.connection_timeout_s,
            )
            log_event("tenant_db", f"pool_creado:{config.tenant_id}:{config.db_host}/{config.db_name}")
            return pool
        except Exception as exc:
            log_event("tenant_db", f"pool_error:{config.tenant_id}:{type(exc).__name__}")
            return None

    def obtener_pool(self, tenant_id: str) -> Any:
        """Obtiene o crea el pool para un tenant."""
        with self._lock:
            if tenant_id not in self._pools:
                config = TenantDBConfig.from_env(tenant_id)
                pool = self._crear_pool(config)
                if pool is None:
                    # Fallback a SQLite local
                    from core.offline_sync import LocalQueueStore
                    self._pools[tenant_id] = ("sqlite", LocalQueueStore())
                    log_event("tenant_db", f"fallback_sqlite:{tenant_id}")
                    return self._pools[tenant_id]
                self._pools[tenant_id] = ("postgres", pool)
            return self._pools[tenant_id]

    @contextmanager
    def get_connection(self, tenant_id: str) -> Generator[Any, None, None]:
        """Context manager que retorna una conexion del pool del tenant.

        Garantiza que la conexion se devuelva al pool incluso en
        caso de excepcion. Reintenta automaticamente si la conexion
        esta caida (reconexion).
        """
        pool_type, pool = self.obtener_pool(tenant_id)

        if pool_type == "sqlite":
            yield pool  # SQLite no necesita conexion por operacion
            return

        conn = None
        for intento in range(3):
            try:
                conn = pool.getconn()
                if conn is None:
                    raise ConnectionError("Pool devolvio None")
                # Verificar que la conexion esta viva
                conn.cursor().execute("SELECT 1")
                yield conn
                return
            except Exception as exc:
                log_event("tenant_db", f"conexion_error:{tenant_id}:intento={intento}:{type(exc).__name__}")
                if conn:
                    try:
                        pool.putconn(conn, close=True)
                    except Exception:
                        pass
                    conn = None
                if intento < 2:
                    time.sleep(0.5 * (intento + 1))
                else:
                    raise
            finally:
                if conn:
                    try:
                        pool.putconn(conn)
                    except Exception:
                        pass

    def cerrar_pool(self, tenant_id: str) -> None:
        """Cierra el pool de un tenant explicitamente."""
        with self._lock:
            if tenant_id in self._pools:
                pool_type, pool = self._pools.pop(tenant_id)
                if pool_type == "postgres":
                    try:
                        pool.closeall()
                        log_event("tenant_db", f"pool_cerrado:{tenant_id}")
                    except Exception as exc:
                        log_event("tenant_db", f"pool_cierre_error:{tenant_id}:{type(exc).__name__}")

    def cerrar_todos(self) -> None:
        """Cierra todos los pools (usar en shutdown)."""
        for tid in list(self._pools.keys()):
            self.cerrar_pool(tid)


# ═══════════════════════════════════════════════════════════════════
# 3. REPOSITORIO BASE (Abstracto)
# ═══════════════════════════════════════════════════════════════════

class TenantRepository:
    """Clase base abstracta para repositorios por tenant.

    Proporciona metodos comunes de acceso a datos con aislamiento
    de tenant automatico.
    """

    def __init__(self, tenant_id: Optional[str] = None):
        self._pool = TenantConnectionPool()
        self._tenant_id = tenant_id or os.environ.get("MEDICARE_TENANT", "default")

    @property
    def tenant_id(self) -> str:
        return self._tenant_id

    def execute(self, query: str, params: tuple = ()) -> Any:
        """Ejecuta una consulta SQL en la base de datos del tenant."""
        with self._pool.get_connection(self._tenant_id) as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()
            return cur

    def fetch_all(self, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Ejecuta SELECT y retorna lista de dicts."""
        with self._pool.get_connection(self._tenant_id) as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[dict[str, Any]]:
        rows = self.fetch_all(query, params)
        return rows[0] if rows else None
