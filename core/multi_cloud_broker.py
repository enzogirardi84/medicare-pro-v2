"""Capa de abstraccion Multi-Cloud para storage y estado.
Actua como Broker: si el proveedor principal falla, conmuta
a fallback secundario de forma transparente para la app.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Callable

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. ESTADOS DEL BROKER
# ═══════════════════════════════════════════════════════════════════

class ProviderStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class StorageProvider(Enum):
    REDIS = "redis"
    POSTGRES = "postgres"
    S3 = "s3"
    R2 = "r2"
    MEMORY = "memory"          # fallback ultimo recurso
    LOCAL_FILE = "local_file"  # fallback de contingencia


# ═══════════════════════════════════════════════════════════════════
# 2. MODELOS DE CONFIGURACION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ProviderConfig:
    """Configuracion de un proveedor de storage."""
    provider: StorageProvider
    priority: int = 100         # menor = preferido
    connection_string: str = ""
    region: str = ""
    health_check_path: str = ""
    timeout: float = 5.0
    retry_count: int = 3


@dataclass
class StorageEntry:
    """Entrada generica de storage con metadatos."""
    key: str
    value: Any
    provider: StorageProvider = StorageProvider.MEMORY
    stored_at: float = 0.0
    ttl: Optional[float] = None


# ═══════════════════════════════════════════════════════════════════
# 3. BROKER MULTI-CLOUD
# ═══════════════════════════════════════════════════════════════════

class MultiCloudBroker:
    """Broker de storage multi-cloud con failover automatico.

    Estrategia:
    1. Escribe en TODOS los proveedores configurados (write-all)
    2. Lee del proveedor con mayor prioridad saludable
    3. Si el primario falla persistentemente, conmuta al secundario
    4. Si todos los clouds fallan, usa memoria local como fallback
    """

    def __init__(self):
        self._providers: dict[StorageProvider, ProviderConfig] = {}
        self._status: dict[StorageProvider, ProviderStatus] = {}
        self._memory_store: dict[str, StorageEntry] = {}          # fallback RAM
        self._local_file_path = os.environ.get(
            "BROKER_FILE_FALLBACK", "/var/medicare/broker_fallback.json"
        )
        self._lock = asyncio.Lock()
        self._current_primary: Optional[StorageProvider] = None

    def configure(self, configs: list[ProviderConfig]):
        """Configura los proveedores disponibles."""
        for cfg in configs:
            self._providers[cfg.provider] = cfg
            self._status[cfg.provider] = ProviderStatus.HEALTHY
        # Ordenar: el de menor priority number es el primario
        sorted_providers = sorted(configs, key=lambda c: c.priority)
        self._current_primary = sorted_providers[0].provider if sorted_providers else StorageProvider.MEMORY
        log_event("multi_cloud", f"configured:{len(configs)} providers, primary:{self._current_primary.value}")

    def _get_healthy_providers(self) -> list[StorageProvider]:
        """Retorna proveedores saludables ordenados por prioridad."""
        healthy = [
            p for p, s in self._status.items()
            if s == ProviderStatus.HEALTHY
        ]
        return sorted(healthy, key=lambda p: self._providers[p].priority)

    # ── Operaciones de storage ─────────────────────────────

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Escribe en TODOS los proveedores disponibles.

        Returns:
            True si al menos un proveedor confirmo la escritura.
        """
        providers = self._get_healthy_providers()
        if not providers:
            # Fallback: memoria local
            self._memory_store[key] = StorageEntry(
                key=key, value=value, provider=StorageProvider.MEMORY,
                stored_at=time.time(), ttl=ttl,
            )
            self._persist_to_file()
            return True

        success = False
        for provider in providers:
            try:
                await self._write_to_provider(provider, key, value, ttl)
                success = True
            except Exception as exc:
                self._record_failure(provider, exc)
        return success

    async def get(self, key: str) -> Optional[Any]:
        """Lee del proveedor primario saludable.

        Caida: fallback al siguiente proveedor.
        Si todos fallan: busca en memoria local.
        """
        providers = self._get_healthy_providers()
        if not providers:
            # Fallback memoria
            entry = self._memory_store.get(key)
            if entry and (entry.ttl is None or time.time() - entry.stored_at < entry.ttl):
                return entry.value
            return None

        for provider in providers:
            try:
                value = await self._read_from_provider(provider, key)
                if value is not None:
                    return value
            except Exception as exc:
                self._record_failure(provider, exc)

        # Fallback final: memoria local
        entry = self._memory_store.get(key)
        return entry.value if entry else None

    async def delete(self, key: str) -> bool:
        """Elimina de todos los proveedores."""
        providers = self._get_healthy_providers()
        success = False
        for provider in providers:
            try:
                await self._delete_from_provider(provider, key)
                success = True
            except Exception:
                pass
        self._memory_store.pop(key, None)
        return success

    # ── Implementaciones por provider ──────────────────────

    async def _write_to_provider(self, provider: StorageProvider, key: str,
                                  value: Any, ttl: Optional[float] = None):
        """Escribe en un proveedor especifico."""
        cfg = self._providers[provider]

        if provider == StorageProvider.MEMORY:
            self._memory_store[key] = StorageEntry(
                key=key, value=value, provider=provider, stored_at=time.time(), ttl=ttl,
            )

        elif provider == StorageProvider.REDIS:
            import json
            try:
                import redis.asynced as aioredis
                r = aioredis.Redis.from_url(cfg.connection_string)
                raw = json.dumps(value, default=str)
                if ttl:
                    await r.setex(key, int(ttl), raw)
                else:
                    await r.set(key, raw)
                await r.close()
            except Exception:
                raise

        elif provider == StorageProvider.POSTGRES:
            import asyncpg
            import json
            conn = await asyncpg.connect(cfg.connection_string)
            try:
                raw = json.dumps(value, default=str)
                await conn.execute("""
                    INSERT INTO broker_store (key, value, created_at)
                    VALUES ($1, $2::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()
                """, key, raw)
            finally:
                await conn.close()

        elif provider == StorageProvider.LOCAL_FILE:
            self._memory_store[key] = StorageEntry(
                key=key, value=value, provider=provider, stored_at=time.time(), ttl=ttl,
            )
            self._persist_to_file()

    async def _read_from_provider(self, provider: StorageProvider, key: str) -> Optional[Any]:
        """Lee de un proveedor especifico."""
        cfg = self._providers[provider]

        if provider == StorageProvider.MEMORY:
            entry = self._memory_store.get(key)
            if entry:
                if entry.ttl is None or time.time() - entry.stored_at < entry.ttl:
                    return entry.value
                self._memory_store.pop(key, None)
            return None

        elif provider == StorageProvider.REDIS:
            try:
                import redis.asynced as aioredis
                r = aioredis.Redis.from_url(cfg.connection_string)
                raw = await r.get(key)
                await r.close()
                return json.loads(raw) if raw else None
            except Exception:
                raise

        elif provider == StorageProvider.POSTGRES:
            import asyncpg
            import json
            conn = await asyncpg.connect(cfg.connection_string)
            try:
                row = await conn.fetchrow(
                    "SELECT value FROM broker_store WHERE key = $1", key
                )
                return json.loads(row["value"]) if row else None
            finally:
                await conn.close()

        return None

    async def _delete_from_provider(self, provider: StorageProvider, key: str):
        """Elimina de un proveedor."""
        if provider == StorageProvider.MEMORY:
            self._memory_store.pop(key, None)
        elif provider == StorageProvider.REDIS:
            import redis.asynced as aioredis
            r = aioredis.Redis.from_url(self._providers[provider].connection_string)
            await r.delete(key)
            await r.close()
        elif provider == StorageProvider.POSTGRES:
            import asyncpg
            conn = await asyncpg.connect(self._providers[provider].connection_string)
            try:
                await conn.execute("DELETE FROM broker_store WHERE key = $1", key)
            finally:
                await conn.close()

    # ── Health checks y failover ───────────────────────────

    def _record_failure(self, provider: StorageProvider, exc: Exception):
        """Registra fallo y degrada el proveedor si es necesario."""
        status = self._status.get(provider, ProviderStatus.HEALTHY)
        if status == ProviderStatus.HEALTHY:
            self._status[provider] = ProviderStatus.DEGRADED
            log_event("multi_cloud", f"degraded:{provider.value}:{type(exc).__name__}")
        elif status == ProviderStatus.DEGRADED:
            self._status[provider] = ProviderStatus.DOWN
            log_event("multi_cloud", f"down:{provider.value}:{type(exc).__name__}")

        # Re-evaluar primario
        healthy = self._get_healthy_providers()
        if healthy:
            self._current_primary = healthy[0]

    def health_check_all(self) -> dict[str, str]:
        """Verifica salud de todos los proveedores configurados."""
        return {p.value: s.value for p, s in self._status.items()}

    # ── Persistencia local de contingencia ─────────────────

    def _persist_to_file(self):
        """Persiste storage en memoria a archivo local (fallback catastrófico)."""
        try:
            os.makedirs(os.path.dirname(self._local_file_path), exist_ok=True)
            data = {}
            for k, entry in self._memory_store.items():
                if entry.ttl is None or time.time() - entry.stored_at < entry.ttl:
                    data[k] = entry.value
            with open(self._local_file_path, "w") as f:
                json.dump(data, f, default=str)
        except Exception as exc:
            log_event("multi_cloud", f"file_persist_error:{type(exc).__name__}")


# ═══════════════════════════════════════════════════════════════════
# 4. SCHEMA SQL PARA FALLBACK POSTGRES
# ═══════════════════════════════════════════════════════════════════

BROKER_SQL = """
CREATE TABLE IF NOT EXISTS broker_store (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_broker_updated ON broker_store (updated_at DESC);
"""


__all__ = [
    "MultiCloudBroker",
    "ProviderConfig",
    "StorageEntry",
    "StorageProvider",
    "ProviderStatus",
    "BROKER_SQL",
]
