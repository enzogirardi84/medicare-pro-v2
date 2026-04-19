"""
Rate Limiter avanzado para protección contra abuso y escalado a millones de usuarios.

- Límites por usuario, IP, tenant y endpoint
- Ventanas deslizantes y bucket de tokens
- Penalización progresiva para abusadores
- Integración con circuit breaker
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import streamlit as st

from core.app_logging import log_event


class LimitType(Enum):
    """Tipos de límites de rate."""
    PER_USER = "per_user"
    PER_IP = "per_ip"
    PER_TENANT = "per_tenant"
    PER_ENDPOINT = "per_endpoint"
    GLOBAL = "global"


class PenaltyLevel(Enum):
    """Niveles de penalización por abuso."""
    NONE = 0
    WARNING = 1
    THROTTLE = 2        # Reducción de velocidad
    BLOCK = 3           # Bloqueo temporal
    BAN = 4             # Ban permanente (requiere intervención manual)


@dataclass
class RateLimitConfig:
    """Configuración de límites de rate."""
    requests_per_window: int = 100
    window_seconds: float = 60.0
    burst_allowance: int = 10  # Peticiones extra permitidas en burst
    throttle_factor: float = 2.0  # Multiplicador de delay en throttle
    block_duration_seconds: float = 300.0  # 5 minutos de bloqueo


@dataclass
class RateLimitEntry:
    """Estado de rate limit para una clave."""
    requests: List[float] = field(default_factory=list)
    violations: int = 0
    penalty_level: PenaltyLevel = PenaltyLevel.NONE
    penalty_until: float = 0.0
    last_request: float = field(default_factory=time.time)
    total_requests: int = 0


class SlidingWindowRateLimiter:
    """
    Rate limiter con ventana deslizante para precisión máxima.
    """

    def __init__(
        self,
        default_config: Optional[RateLimitConfig] = None,
        cleanup_interval: float = 300.0,  # 5 minutos
    ):
        self.default_config = default_config or RateLimitConfig()
        self._entries: Dict[str, RateLimitEntry] = {}
        self._configs: Dict[str, RateLimitConfig] = {}
        self._lock = threading.RLock()
        self._last_cleanup = time.time()
        self._cleanup_interval = cleanup_interval

    def _get_key(
        self,
        limit_type: LimitType,
        identifier: str,
        endpoint: Optional[str] = None,
    ) -> str:
        """Genera clave única para el limitador."""
        base = f"{limit_type.value}:{identifier}"
        if endpoint:
            base += f":{endpoint}"
        return base

    def _maybe_cleanup(self):
        """Limpia entradas antiguas periódicamente."""
        if time.time() - self._last_cleanup < self._cleanup_interval:
            return

        with self._lock:
            now = time.time()
            cutoff = now - 3600  # 1 hora de inactividad

            to_remove = [
                key for key, entry in self._entries.items()
                if entry.last_request < cutoff and entry.penalty_until < now
            ]
            for key in to_remove:
                del self._entries[key]

            self._last_cleanup = now

    def _get_config(self, key: str) -> RateLimitConfig:
        """Obtiene configuración para una clave.

        Busca primero el key exacto (con endpoint). Si no existe, cae al key
        base sin endpoint (para que set_config(tipo, id) aplique a todos los
        endpoints de ese id sin exigir configurarlos individualmente).
        """
        if key in self._configs:
            return self._configs[key]
        # Fallback al identificador sin endpoint: "per_user:u" a partir de "per_user:u:/path"
        base_key = key.rsplit(":", 1)[0] if key.count(":") >= 2 else key
        if base_key in self._configs:
            return self._configs[base_key]
        return self.default_config

    def set_config(
        self,
        limit_type: LimitType,
        identifier: str,
        config: RateLimitConfig,
        endpoint: Optional[str] = None,
    ):
        """Configura límites personalizados."""
        key = self._get_key(limit_type, identifier, endpoint)
        with self._lock:
            self._configs[key] = config

    def check_rate_limit(
        self,
        limit_type: LimitType,
        identifier: str,
        endpoint: Optional[str] = None,
        cost: int = 1,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Verifica si una petición está dentro del límite.

        Retorna (permitido, metadata).
        """
        self._maybe_cleanup()

        key = self._get_key(limit_type, identifier, endpoint)
        config = self._get_config(key)
        now = time.time()

        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                entry = RateLimitEntry()
                self._entries[key] = entry

            # Verificar penalización activa
            if now < entry.penalty_until:
                return False, {
                    "allowed": False,
                    "reason": f"penalty:{entry.penalty_level.name}",
                    "retry_after": int(entry.penalty_until - now),
                    "penalty_until": entry.penalty_until,
                }

            # Limpiar requests antiguas fuera de la ventana
            window_start = now - config.window_seconds
            entry.requests = [t for t in entry.requests if t > window_start]

            # Verificar burst allowance
            burst_used = max(0, len(entry.requests) - config.requests_per_window)
            burst_remaining = config.burst_allowance - burst_used

            if burst_remaining < cost:
                # Violación de rate limit
                entry.violations += 1
                self._apply_penalty(key, entry, config)

                return False, {
                    "allowed": False,
                    "reason": "rate_limit_exceeded",
                    "retry_after": int(config.window_seconds),
                    "window_requests": len(entry.requests),
                    "violations": entry.violations,
                }

            # Registrar petición
            entry.requests.extend([now] * cost)
            entry.last_request = now
            entry.total_requests += cost

            remaining = config.requests_per_window + config.burst_allowance - len(entry.requests)
            reset_time = int(window_start + config.window_seconds)

            return True, {
                "allowed": True,
                "remaining": max(0, remaining),
                "reset_time": reset_time,
                "window_requests": len(entry.requests),
                "penalty_level": entry.penalty_level.name,
            }

    def _apply_penalty(
        self,
        key: str,
        entry: RateLimitEntry,
        config: RateLimitConfig,
    ):
        """Aplica penalización progresiva."""
        violations = entry.violations

        if violations >= 10:
            entry.penalty_level = PenaltyLevel.BAN
            entry.penalty_until = time.time() + 86400  # 24 horas
            log_event("rate_limit", f"ban:{key}:violations={violations}")
        elif violations >= 5:
            entry.penalty_level = PenaltyLevel.BLOCK
            entry.penalty_until = time.time() + config.block_duration_seconds
            log_event("rate_limit", f"block:{key}:violations={violations}")
        elif violations >= 3:
            entry.penalty_level = PenaltyLevel.THROTTLE
            entry.penalty_until = time.time() + 60  # 1 minuto de throttle
            log_event("rate_limit", f"throttle:{key}:violations={violations}")
        else:
            entry.penalty_level = PenaltyLevel.WARNING
            log_event("rate_limit", f"warning:{key}:violations={violations}")

    def get_metrics(self, key: Optional[str] = None) -> Dict[str, Any]:
        """Obtiene métricas de rate limiting."""
        if key:
            entry = self._entries.get(key)
            if entry:
                return {
                    "requests_in_window": len(entry.requests),
                    "total_requests": entry.total_requests,
                    "violations": entry.violations,
                    "penalty_level": entry.penalty_level.name,
                    "penalty_active": time.time() < entry.penalty_until,
                }
            return {}

        # Métricas globales
        total_entries = len(self._entries)
        active_penalties = sum(
            1 for e in self._entries.values()
            if time.time() < e.penalty_until
        )
        total_violations = sum(e.violations for e in self._entries.values())

        return {
            "total_monitored": total_entries,
            "active_penalties": active_penalties,
            "total_violations": total_violations,
        }

    def reset(self, key: Optional[str] = None):
        """Resetea contadores (útil para testing o intervención manual)."""
        with self._lock:
            if key:
                if key in self._entries:
                    del self._entries[key]
            else:
                self._entries.clear()


class TokenBucketRateLimiter:
    """
    Rate limiter basado en bucket de tokens para bursts controlados.
    """

    def __init__(
        self,
        tokens_per_second: float = 10.0,
        bucket_size: int = 20,
    ):
        self.tokens_per_second = tokens_per_second
        self.bucket_size = bucket_size
        self._buckets: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _get_bucket(self, key: str) -> Dict[str, Any]:
        now = time.time()
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = {
                    "tokens": self.bucket_size,
                    "last_update": now,
                }
            return self._buckets[key]

    def consume(self, key: str, tokens: int = 1) -> Tuple[bool, Dict[str, Any]]:
        """Intenta consumir tokens del bucket."""
        now = time.time()
        bucket = self._get_bucket(key)

        with self._lock:
            # Recargar tokens basado en tiempo transcurrido
            elapsed = now - bucket["last_update"]
            tokens_to_add = elapsed * self.tokens_per_second
            bucket["tokens"] = min(
                self.bucket_size,
                bucket["tokens"] + tokens_to_add
            )
            bucket["last_update"] = now

            if bucket["tokens"] >= tokens:
                bucket["tokens"] -= tokens
                return True, {
                    "allowed": True,
                    "remaining_tokens": bucket["tokens"],
                    "reset_time": int(now + (self.bucket_size - bucket["tokens"]) / self.tokens_per_second),
                }
            else:
                retry_after = (tokens - bucket["tokens"]) / self.tokens_per_second
                return False, {
                    "allowed": False,
                    "reason": "insufficient_tokens",
                    "retry_after": int(retry_after) + 1,
                    "required_tokens": tokens,
                    "available_tokens": bucket["tokens"],
                }


# Instancias globales
_sliding_limiter: Optional[SlidingWindowRateLimiter] = None
_token_limiter: Optional[TokenBucketRateLimiter] = None
_limiter_lock = threading.Lock()


def get_sliding_limiter() -> SlidingWindowRateLimiter:
    """Obtiene la instancia global del rate limiter de ventana deslizante."""
    global _sliding_limiter
    if _sliding_limiter is None:
        with _limiter_lock:
            if _sliding_limiter is None:
                _sliding_limiter = SlidingWindowRateLimiter()
    return _sliding_limiter


def get_token_limiter() -> TokenBucketRateLimiter:
    """Obtiene la instancia global del rate limiter de bucket de tokens."""
    global _token_limiter
    if _token_limiter is None:
        with _limiter_lock:
            if _token_limiter is None:
                _token_limiter = TokenBucketRateLimiter()
    return _token_limiter


def check_rate_limit(
    limit_type: LimitType,
    identifier: str,
    endpoint: Optional[str] = None,
    cost: int = 1,
) -> Tuple[bool, Dict[str, Any]]:
    """Verificación rápida de rate limit."""
    limiter = get_sliding_limiter()
    return limiter.check_rate_limit(limit_type, identifier, endpoint, cost)


def rate_limit_guard(
    limit_type: LimitType,
    identifier: str,
    endpoint: Optional[str] = None,
    on_reject: Optional[Callable] = None,
):
    """
    Decorador/guard para rate limiting.

    Uso:
        if not rate_limit_guard(LimitType.PER_USER, user_id, "api/pacientes"):
            st.error("Rate limit exceeded")
            return
    """
    allowed, metadata = check_rate_limit(limit_type, identifier, endpoint)

    if not allowed and on_reject:
        on_reject(metadata)

    return allowed


def get_client_identifier() -> str:
    """
    Obtiene identificador del cliente actual.
    Combina información de sesión disponible.
    """
    parts = []

    # Usuario logueado
    user = st.session_state.get("u_actual", {})
    if user and isinstance(user, dict):
        user_id = user.get("usuario_login") or user.get("dni", "")
        if user_id:
            parts.append(f"user:{user_id}")

    # Tenant/clínica
    empresa = user.get("empresa", "") if isinstance(user, dict) else ""
    if empresa:
        parts.append(f"tenant:{empresa}")

    # IP/headers si disponibles
    try:
        ctx = st.runtime.scriptrunner.get_script_run_ctx()
        if ctx and hasattr(ctx, 'session_id'):
            parts.append(f"session:{ctx.session_id[:8]}")
    except Exception:
        pass

    if not parts:
        return "anonymous"

    return hashlib.md5("|".join(parts).encode()).hexdigest()[:16]
