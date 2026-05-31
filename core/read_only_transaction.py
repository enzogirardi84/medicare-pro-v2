"""Decorador para transacciones de solo lectura con balanceo Round Robin
entre replicas de lectura de PostgreSQL. Evita cargar el nodo maestro.
"""
from __future__ import annotations

import asyncio
import functools
import os
import random
from typing import Any, Callable, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. BALANCEADOR ROUND ROBIN PARA READ REPLICAS
# ═══════════════════════════════════════════════════════════════════

class ReadReplicaBalancer:
    """Balancea consultas SELECT entre replicas de lectura.

    Lee las URLs de replicas desde variables de entorno.
    Implementa Round Robin con fallback a primary si todas fallan.
    """

    def __init__(self):
        self._replicas: list[str] = self._cargar_replicas()
        self._index = 0
        self._lock = asyncio.Lock()

    def _cargar_replicas(self) -> list[str]:
        """Carga URLs de replicas desde variables de entorno.

        Usar formato: READ_REPLICA_0, READ_REPLICA_1, ...
        """
        replicas = []
        i = 0
        while True:
            url = os.environ.get(f"READ_REPLICA_{i}")
            if not url:
                break
            replicas.append(url)
            i += 1

        # Si no hay replicas configuradas, usar la primaria
        if not replicas:
            primary = os.environ.get("DB_URL", "postgresql://localhost:5432/medicare")
            replicas = [primary]

        return replicas

    async def obtener_conexion(self) -> str:
        """Obtiene la URL de la siguiente replica (Round Robin).

        Si la replica seleccionada falla, intenta la siguiente.
        """
        async with self._lock:
            url = self._replicas[self._index % len(self._replicas)]
            self._index += 1
            return url

    @property
    def cantidad_replicas(self) -> int:
        return len(self._replicas)


# Instancia global del balanceador
_balancer: Optional[ReadReplicaBalancer] = None


def get_balancer() -> ReadReplicaBalancer:
    global _balancer
    if _balancer is None:
        _balancer = ReadReplicaBalancer()
    return _balancer


# ═══════════════════════════════════════════════════════════════════
# 2. DECORADOR READ_ONLY_TRANSACTION
# ═══════════════════════════════════════════════════════════════════

def read_only_transaction(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorador para funciones de solo lectura.

    - Conecta a una Read Replica (Round Robin)
    - Configura la sesion en READ ONLY
    - Previene accidentalmente INSERT/UPDATE/DELETE
    - Si todas las replicas fallan, usa el primary como fallback

    Uso:
        @read_only_transaction
        async def get_reporte_epidemiologico(tenant_id):
            ...
    """
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        balancer = get_balancer()
        replica_url = await balancer.obtener_conexion()

        import asyncpg

        intentos = 0
        ultimo_error = None

        while intentos < len(balancer._replicas):
            try:
                conn = await asyncpg.connect(replica_url)
                # Configurar sesion READ ONLY
                await conn.execute("SET TRANSACTION READ ONLY")
                await conn.execute("SET statement_timeout = '30000'")

                result = await func(conn, *args, **kwargs)
                return result

            except Exception as exc:
                log_event("read_only", f"replica_fallo:{replica_url}:{type(exc).__name__}")
                ultimo_error = exc
                intentos += 1
                replica_url = await balancer.obtener_conexion()

            finally:
                try:
                    await conn.close()
                except Exception:
                    pass

        # Si todas las replicas fallaron, intentar primary
        try:
            primary_url = os.environ.get("DB_URL", "postgresql://localhost:5432/medicare")
            conn = await asyncpg.connect(primary_url)
            await conn.execute("SET TRANSACTION READ ONLY")
            return await func(conn, *args, **kwargs)
        except Exception as exc:
            log_event("read_only", f"primary_fallback_fallo:{type(exc).__name__}")
            raise ultimo_error or exc

    return wrapper


# ═══════════════════════════════════════════════════════════════════
# 3. EJEMPLO DE USO
# ═══════════════════════════════════════════════════════════════════

@read_only_transaction
async def get_reporte_mensual(conn: Any, tenant_id: str) -> dict[str, Any]:
    """Ejemplo: reporte mensual de evoluciones (solo lectura)."""
    rows = await conn.fetch("""
        SELECT
            DATE_TRUNC('month', created_at) as mes,
            COUNT(*) as total_evoluciones,
            COUNT(DISTINCT paciente_id) as pacientes_atendidos
        FROM evoluciones
        WHERE tenant_id = $1
          AND created_at >= NOW() - INTERVAL '12 months'
        GROUP BY DATE_TRUNC('month', created_at)
        ORDER BY mes DESC
    """, tenant_id)
    return [dict(r) for r in rows]
