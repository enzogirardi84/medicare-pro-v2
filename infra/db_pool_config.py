"""Configuracion optima del pool de conexiones PostgreSQL + Backoff Exponencial.
SQLAlchemy asincrono con NullPool/QueuePool para alta concurrencia.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. CONFIGURACION DEL POOL
# ═══════════════════════════════════════════════════════════════════

@dataclass
class PoolConfig:
    """Configuracion del pool de conexiones PostgreSQL.

    Para sync de lotes masivos:
    - pool_size=20: permite 20 conexiones simultaneas
    - max_overflow=10: hasta 10 adicionales en picos
    - pool_timeout=30: esperar max 30s por conexion
    - pool_pre_ping=True: verificar salud antes de usar
    """
    pool_size: int = 20
    max_overflow: int = 10
    pool_timeout: float = 30.0
    pool_pre_ping: bool = True
    pool_recycle: int = 3600  # Reciclar conexiones cada 1h
    max_retries: int = 5
    base_delay: float = 1.0  # Backoff inicial en segundos


def create_async_pool(config: Optional[PoolConfig] = None) -> Any:
    """Crea el pool de conexiones asincrono optimizado.

    Usa QueuePool con tamanio fijo + overflow para picos.
    En produccion con PgBouncer, usar NullPool (sin pool local).
    """
    from sqlalchemy.ext.asyncio import (
        create_async_engine,
        AsyncSession,
        async_sessionmaker,
    )
    from sqlalchemy.pool import QueuePool, NullPool

    cfg = config or PoolConfig()
    db_url = "postgresql+asyncpg://user:pass@localhost:5432/medicare"

    # PgBouncer Transaction mode -> NullPool (sin pool local)
    # Directo -> QueuePool con tamanio fijo
    use_pgbouncer = False  # Configurar segun entorno
    pool_class = NullPool if use_pgbouncer else QueuePool

    engine = create_async_engine(
        db_url,
        poolclass=pool_class,
        pool_size=cfg.pool_size,
        max_overflow=cfg.max_overflow,
        pool_timeout=cfg.pool_timeout,
        pool_pre_ping=cfg.pool_pre_ping,
        pool_recycle=cfg.pool_recycle,
        echo=False,
        connect_args={
            "command_timeout": 30,
            "ssl": "require" if not use_pgbouncer else "disable",
        },
    )

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    log_event("db_pool", f"Pool creado: size={cfg.pool_size}, overflow={cfg.max_overflow}")
    return session_factory


# ═══════════════════════════════════════════════════════════════════
# 2. BACKOFF EXPONENCIAL PARA CLIENTES SYNC
# ═══════════════════════════════════════════════════════════════════

class ExponentialBackoff:
    """Backoff exponencial con jitter para reintentos de sincronizacion.

    Uso:
        backoff = ExponentialBackoff()
        async for wait in backoff:
            try:
                await client.sync_batch(data)
                break
            except (HTTPException, ConnectionError):
                continue
    """

    def __init__(self, max_retries: int = 5, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._attempt = 0

    def __aiter__(self):
        return self._generator()

    async def _generator(self):
        import random
        while self._attempt < self.max_retries:
            delay = self.base_delay * (2 ** self._attempt)
            jitter = random.uniform(0, delay * 0.1)
            total_delay = delay + jitter
            log_event("backoff", f"Intento {self._attempt + 1}/{self.max_retries}, esperando {total_delay:.1f}s")
            yield total_delay
            self._attempt += 1


async def sync_with_backoff(client: Any, data: dict) -> bool:
    """Sincroniza con backoff exponencial ante errores 429/503."""
    backoff = ExponentialBackoff(max_retries=5, base_delay=2.0)
    async for wait in backoff:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as session:
                response = await session.post(
                    "https://api.medicare.pro/sync/batch",
                    json=data,
                    headers={"X-Tenant-Id": data.get("tenant_id", "")},
                )
                if response.status_code == 200:
                    return True
                elif response.status_code in (429, 503):
                    log_event("backoff", f"HTTP {response.status_code}, reintentando...")
                    await asyncio.sleep(wait)
                    continue
                else:
                    log_event("backoff", f"Error {response.status_code}: {response.text[:100]}")
                    return False
        except (httpx.TimeoutException, httpx.ConnectionError):
            log_event("backoff", "Timeout/conexion, reintentando...")
            await asyncio.sleep(wait)
            continue
    return False
