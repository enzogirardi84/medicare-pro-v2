"""Rate Limiting dinamico por tenant con Redis (Token Bucket).
Cuotas personalizadas segun plan del tenant.
Metricas Prometheus para monitoreo de abuso.
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. CONFIGURACION POR TENANT
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TenantRateLimit:
    """Limites de tasa por tenant."""
    tenant_id: str
    requests_per_minute: int = 60       # Plan basico
    requests_per_hour: int = 1000
    burst_size: int = 10                # Rafagas permitidas
    concurrent_limit: int = 5            # Conexiones simultaneas


PLAN_LIMITS = {
    "basic": TenantRateLimit("basic", rpm=30, rph=500, burst=5, concurrent=3),
    "professional": TenantRateLimit("professional", rpm=60, rph=1000, burst=10, concurrent=5),
    "enterprise": TenantRateLimit("enterprise", rpm=200, rph=5000, burst=25, concurrent=20),
}


def get_plan_for_tenant(tenant_id: str) -> str:
    """Obtiene el plan del tenant desde la DB o env."""
    # En produccion, leer de tabla tenants.plan
    return os.environ.get(f"RATE_LIMIT_{tenant_id.upper()}", "professional")


# ═══════════════════════════════════════════════════════════════════
# 2. TOKEN BUCKET CON REDIS
# ═══════════════════════════════════════════════════════════════════

class RateLimiterRedis:
    """Rate limiter con Redis (Token Bucket) y fallback en memoria.

    Cada tenant tiene su propio bucket con tokens que se recargan
    a una tasa fija. Los tokens se consumen por request.
    """

    def __init__(self):
        self._redis = None
        self._local_buckets: dict[str, dict[str, float]] = {}
        self._init_redis()

    def _init_redis(self) -> None:
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.Redis(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", "6379")),
                db=2,
                decode_responses=True,
                socket_timeout=2,
            )
            log_event("rate_limiter", "Redis conectado")
        except Exception:
            log_event("rate_limiter", "Redis no disponible: usando fallback local")

    def _get_limits(self, tenant_id: str) -> TenantRateLimit:
        plan = get_plan_for_tenant(tenant_id)
        return PLAN_LIMITS.get(plan, PLAN_LIMITS["professional"])

    async def check(self, tenant_id: str, cost: int = 1) -> tuple[bool, dict[str, Any]]:
        """Verifica si el request del tenant puede pasar.

        Algoritmo Token Bucket:
        - Se recargan tokens a rpm/60 por segundo
        - maximo de tokens = burst_size
        - Si no hay tokens suficientes, se rechaza

        Returns:
            (allowed, headers) donde headers incluye informacion
            de rate limiting para el cliente.
        """
        limits = self._get_limits(tenant_id)
        now = time.time()

        # Redis path
        if self._redis:
            try:
                key = f"rl:{tenant_id}"
                pipe = self._redis.pipeline()
                pipe.hgetall(key)
                pipe.ttl(key)
                results = await pipe.execute()
                data = results[0] if results else {}
                ttl = results[1] if len(results) > 1 else 0

                if data:
                    tokens = float(data.get("tokens", limits.burst_size))
                    last_refill = float(data.get("last_refill", now))
                else:
                    tokens = float(limits.burst_size)
                    last_refill = now

                # Recargar tokens
                elapsed = now - last_refill
                tokens = min(limits.burst_size, tokens + elapsed * (limits.requests_per_minute / 60.0))

                if tokens >= cost:
                    tokens -= cost
                    await self._redis.hset(key, mapping={
                        "tokens": tokens,
                        "last_refill": now,
                    })
                    await self._redis.expire(key, 60)
                    return True, {
                        "X-RateLimit-Limit": limits.requests_per_minute,
                        "X-RateLimit-Remaining": int(tokens),
                        "X-RateLimit-Reset": int(now + 60),
                    }
                else:
                    return False, {
                        "X-RateLimit-Limit": limits.requests_per_minute,
                        "X-RateLimit-Remaining": 0,
                        "Retry-After": str(int(1 / max(limits.requests_per_minute / 60.0, 0.01))),
                    }
            except Exception:
                pass

        # Fallback local (en memoria)
        bucket = self._local_buckets.setdefault(tenant_id, {
            "tokens": float(limits.burst_size),
            "last_refill": now,
        })

        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(limits.burst_size, bucket["tokens"] + elapsed * (limits.requests_per_minute / 60.0))
        bucket["last_refill"] = now

        if bucket["tokens"] >= cost:
            bucket["tokens"] -= cost
            return True, {
                "X-RateLimit-Limit": limits.requests_per_minute,
                "X-RateLimit-Remaining": int(bucket["tokens"]),
            }
        else:
            return False, {
                "X-RateLimit-Limit": limits.requests_per_minute,
                "X-RateLimit-Remaining": 0,
                "Retry-After": "1",
            }

    async def middleware(self, request: Any, call_next: Any) -> Any:
        """Middleware ASGI para FastAPI.

        Uso:
            app.middleware("http")(rate_limiter.middleware)
        """
        from fastapi.responses import JSONResponse

        tenant_id = request.headers.get("X-Tenant-Id", "unknown")
        allowed, headers = await self.check(tenant_id)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "Too Many Requests", "tenant": tenant_id},
                headers=headers,
            )

        response = await call_next(request)
        for k, v in headers.items():
            response.headers[k] = str(v)
        return response
