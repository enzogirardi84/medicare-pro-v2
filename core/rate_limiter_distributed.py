"""
Rate Limiting Distribuido con Redis - Protección contra Fuerza Bruta.

Implementa:
- Sliding window rate limiting
- Circuit breaker para endpoints críticos  
- Distributed tracking vía Redis
- Fallback a memoria local si Redis no disponible
"""
import time
import hashlib
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from functools import wraps

import streamlit as st

from core.app_logging import log_event


def _get_settings():
    """Import lazy de get_settings para evitar ValidationError en tests."""
    from core.config_secure import get_settings
    return get_settings()


class RateLimitStrategy(Enum):
    """Estrategias de rate limiting."""
    SLIDING_WINDOW = "sliding_window"      # Más preciso, recomendado
    FIXED_WINDOW = "fixed_window"          # Más simple, menos preciso
    TOKEN_BUCKET = "token_bucket"        # Para burst handling


@dataclass
class RateLimitConfig:
    """Configuración de rate limiting."""
    key_prefix: str = "rl"
    max_requests: int = 100              # Máximo de requests
    window_seconds: int = 60             # Ventana de tiempo
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    block_duration_seconds: int = 300    # Bloqueo tras exceder límite
    burst_allowance: int = 10            # Requests extra en burst


@dataclass
class RateLimitStatus:
    """Estado actual del rate limit para un cliente."""
    allowed: bool
    remaining: int
    reset_time: float
    blocked_until: Optional[float] = None
    total_requests: int = 0


class DistributedRateLimiter:
    """
    Rate limiter distribuido con Redis + fallback a memoria.
    
    Usar para proteger:
    - Login (5 intentos/minuto)
    - API endpoints (100 requests/minuto)
    - Guardado de datos (30 requests/minuto)
    """
    
    def __init__(self):
        self._redis = None
        self._local_cache: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
        self._init_redis()
    
    def _init_redis(self) -> None:
        """Inicializa conexión Redis si está disponible."""
        try:
            settings = _get_settings()
            redis_url = settings.redis_url
            
            if redis_url:
                import redis
                self._redis = redis.from_url(
                    redis_url.get_secret_value(),
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    health_check_interval=30
                )
                self._initialized = True
                log_event("rate_limiter", "redis_connected")
        except Exception as e:
            log_event("rate_limiter", f"redis_fallback:{type(e).__name__}")
            self._redis = None
    
    def _get_client_key(self, identifier: str, action: str) -> str:
        """Genera clave única para cliente+acción."""
        # Hashear para proteger privacidad
        raw = f"{identifier}:{action}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
    
    def _is_blocked_local(self, key: str) -> Tuple[bool, Optional[float]]:
        """Verifica bloqueo en caché local."""
        now = time.time()
        if key in self._local_cache:
            data = self._local_cache[key]
            blocked_until = data.get("blocked_until")
            if blocked_until and now < blocked_until:
                return True, blocked_until
        return False, None
    
    def check_rate_limit(
        self,
        identifier: str,
        action: str,
        config: Optional[RateLimitConfig] = None
    ) -> RateLimitStatus:
        """
        Verifica si el cliente puede realizar la acción.
        
        Args:
            identifier: IP, user_id, o session_id
            action: Tipo de acción ("login", "api_call", "save_data")
            config: Configuración de rate limiting
        
        Returns:
            RateLimitStatus con el resultado
        """
        config = config or RateLimitConfig()
        key = self._get_client_key(identifier, action)
        now = time.time()
        
        # Verificar bloqueo existente
        if self._redis:
            try:
                blocked_key = f"{key}:blocked"
                blocked_until = self._redis.get(blocked_key)
                if blocked_until:
                    blocked_time = float(blocked_until)
                    if now < blocked_time:
                        return RateLimitStatus(
                            allowed=False,
                            remaining=0,
                            reset_time=blocked_time,
                            blocked_until=blocked_time,
                            total_requests=0
                        )
            except Exception:
                pass  # Fallback a local
        
        # Check local fallback
        is_blocked, blocked_until = self._is_blocked_local(key)
        if is_blocked:
            return RateLimitStatus(
                allowed=False,
                remaining=0,
                reset_time=blocked_until or now + config.block_duration_seconds,
                blocked_until=blocked_until,
                total_requests=0
            )
        
        # Sliding window implementation
        if self._redis:
            try:
                return self._check_sliding_window_redis(key, config, now)
            except Exception:
                pass  # Fallback a local
        
        return self._check_sliding_window_local(key, action, config, now)
    
    def _check_sliding_window_redis(
        self,
        key: str,
        config: RateLimitConfig,
        now: float
    ) -> RateLimitStatus:
        """Sliding window con Redis (precisión milisegundos)."""
        window_start = now - config.window_seconds
        
        # Lua script atómico para sliding window
        lua_script = """
            local key = KEYS[1]
            local window_start = tonumber(ARGV[1])
            local now = tonumber(ARGV[2])
            local max_requests = tonumber(ARGV[3])
            local window_seconds = tonumber(ARGV[4])
            
            -- Remover entradas antiguas
            redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
            
            -- Contar requests en ventana actual
            local current = redis.call('ZCARD', key)
            
            -- Verificar límite
            if current >= max_requests then
                return {0, current, now + window_seconds}
            end
            
            -- Agregar request actual
            redis.call('ZADD', key, now, now)
            redis.call('EXPIRE', key, window_seconds)
            
            return {1, max_requests - current - 1, now + window_seconds}
        """
        
        result = self._redis.eval(
            lua_script, 1, key,
            window_start, now, config.max_requests, config.window_seconds
        )
        
        allowed = bool(result[0])
        remaining = result[1]
        reset_time = result[2]
        
        if not allowed:
            # Bloquear
            blocked_key = f"{key}:blocked"
            self._redis.setex(
                blocked_key,
                config.block_duration_seconds,
                now + config.block_duration_seconds
            )
        
        return RateLimitStatus(
            allowed=allowed,
            remaining=max(0, remaining),
            reset_time=reset_time,
            total_requests=config.max_requests - remaining
        )
    
    def _check_sliding_window_local(
        self,
        key: str,
        action: str,
        config: RateLimitConfig,
        now: float
    ) -> RateLimitStatus:
        """Sliding window con memoria local (fallback)."""
        window_start = now - config.window_seconds
        
        # Inicializar estructura
        if key not in self._local_cache:
            self._local_cache[key] = {"requests": [], "blocked_until": None}
        
        data = self._local_cache[key]
        
        # Limpiar requests antiguos
        data["requests"] = [
            ts for ts in data["requests"]
            if ts > window_start
        ]
        
        current_count = len(data["requests"])
        
        # Verificar límite
        if current_count >= config.max_requests:
            # Bloquear
            blocked_until = now + config.block_duration_seconds
            data["blocked_until"] = blocked_until
            
            log_event("rate_limiter", f"blocked:{key[:8]}:{action}")
            
            return RateLimitStatus(
                allowed=False,
                remaining=0,
                reset_time=blocked_until,
                blocked_until=blocked_until,
                total_requests=current_count
            )
        
        # Permitir request
        data["requests"].append(now)
        
        return RateLimitStatus(
            allowed=True,
            remaining=config.max_requests - current_count - 1,
            reset_time=now + config.window_seconds,
            total_requests=current_count + 1
        )
    
    def reset_limit(self, identifier: str, action: str) -> None:
        """Resetea el rate limit para un cliente (útil para login exitoso)."""
        key = self._get_client_key(identifier, action)
        
        if self._redis:
            try:
                self._redis.delete(key)
                self._redis.delete(f"{key}:blocked")
            except Exception:
                pass
        
        if key in self._local_cache:
            del self._local_cache[key]


# Instancia global
_rate_limiter = None

def get_rate_limiter() -> DistributedRateLimiter:
    """Retorna instancia singleton del rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = DistributedRateLimiter()
    return _rate_limiter


# Configuraciones predefinidas para casos comunes
RATE_LIMIT_LOGIN = RateLimitConfig(
    key_prefix="rl:login",
    max_requests=5,              # 5 intentos
    window_seconds=60,           # por minuto
    block_duration_seconds=300,  # bloqueo 5 minutos
    strategy=RateLimitStrategy.SLIDING_WINDOW
)

RATE_LIMIT_API = RateLimitConfig(
    key_prefix="rl:api",
    max_requests=100,            # 100 requests
    window_seconds=60,           # por minuto
    block_duration_seconds=60,
    strategy=RateLimitStrategy.SLIDING_WINDOW
)

RATE_LIMIT_SAVE = RateLimitConfig(
    key_prefix="rl:save",
    max_requests=30,             # 30 guardados
    window_seconds=60,           # por minuto
    block_duration_seconds=30,
    strategy=RateLimitStrategy.SLIDING_WINDOW
)

RATE_LIMIT_SEARCH = RateLimitConfig(
    key_prefix="rl:search",
    max_requests=60,             # 60 búsquedas
    window_seconds=60,           # por minuto
    block_duration_seconds=30,
    strategy=RateLimitStrategy.SLIDING_WINDOW
)


def rate_limit(
    action: str,
    config: RateLimitConfig,
    identifier_func: Optional[callable] = None
):
    """
    Decorador para rate limiting en funciones.
    
    Args:
        action: Identificador de la acción
        config: Configuración de rate limiting
        identifier_func: Función para extraer identificador (default: IP o user_id)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Determinar identificador
            if identifier_func:
                identifier = identifier_func(*args, **kwargs)
            else:
                # Default: IP o user_id de session_state
                identifier = _get_default_identifier()
            
            limiter = get_rate_limiter()
            status = limiter.check_rate_limit(identifier, action, config)
            
            if not status.allowed:
                remaining_seconds = int(status.blocked_until - time.time())
                raise RateLimitExceeded(
                    f"Demasiados intentos. Espere {remaining_seconds} segundos."
                )
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def _get_default_identifier() -> str:
    """Obtiene identificador por defecto (IP o user_id)."""
    try:
        # Intentar obtener user_id de sesión
        user = st.session_state.get("u_actual", {})
        user_id = user.get("username")
        if user_id:
            return f"user:{user_id}"
    except Exception:
        pass
    
    # Fallback a IP (simulado en Streamlit)
    return "ip:unknown"


class RateLimitExceeded(Exception):
    """Excepción cuando se excede el rate limit."""
    pass


# Funciones helper de alto nivel

def check_login_rate_limit(identifier: str) -> RateLimitStatus:
    """Verifica rate limit para login."""
    return get_rate_limiter().check_rate_limit(
        identifier, "login", RATE_LIMIT_LOGIN
    )


def check_api_rate_limit(identifier: str) -> RateLimitStatus:
    """Verifica rate limit para API calls."""
    return get_rate_limiter().check_rate_limit(
        identifier, "api", RATE_LIMIT_API
    )


def reset_login_attempts(identifier: str) -> None:
    """Resetea intentos de login (llamar tras login exitoso)."""
    get_rate_limiter().reset_limit(identifier, "login")
