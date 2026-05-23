"""Servicio de IA con Circuit Breaker para resiliencia ante fallas de APIs externas.

Implementa un Circuit Breaker manual que:
- Permite llamadas normalmente mientras no haya fallos
- Si falla 3 veces consecutivas, abre el circuito por 60 segundos
- Mientras esta abierto, devuelve respuesta cacheada o mensaje seguro
- Despues de 60s, permite un reintento (half-open)
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from core.app_logging import log_event


class CircuitBreaker:
    """Circuit Breaker para APIs externas de IA."""
    
    STATE_CLOSED = "closed"      # Funcionando normalmente
    STATE_OPEN = "open"          # Corte activo, no se llama a la API
    STATE_HALF_OPEN = "half_open"  # Probando si la API ya recupero
    
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = self.STATE_CLOSED
    
    def call(self, fn, fallback=None):
        """Ejecuta la funcion si el circuito esta cerrado.
        Si esta abierto, retorna fallback.
        Si falla, incrementa contador y posiblemente abre el circuito.
        """
        now = time.monotonic()
        
        # Half-open: permitir un reintento despues del timeout
        if self.state == self.STATE_OPEN:
            if now - self.last_failure_time >= self.recovery_timeout:
                self.state = self.STATE_HALF_OPEN
                log_event("circuit_breaker", "half_open: reintentando llamada a IA")
            else:
                log_event("circuit_breaker", "open: llamada bloqueada, usando fallback")
                return fallback
        
        try:
            result = fn()
            # Exito: resetear contadores
            self.failure_count = 0
            if self.state != self.STATE_CLOSED:
                self.state = self.STATE_CLOSED
                log_event("circuit_breaker", "closed: IA recuperada")
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = now
            log_event("circuit_breaker", f"failure:{self.failure_count}/{self.failure_threshold}:{type(e).__name__}")
            
            if self.failure_count >= self.failure_threshold:
                self.state = self.STATE_OPEN
                log_event("circuit_breaker", f"open: circuito abierto por {self.recovery_timeout}s")
            
            if fallback is not None:
                return fallback
            raise


# Singleton del Circuit Breaker para IA
_ia_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)


def call_ia_seguro(llm_fn, fallback_msg: str = "El asistente IA esta temporalmente fuera de linea. Use las guias clinicas locales."):
    """Wrapper seguro para llamadas a IA con Circuit Breaker.
    
    Args:
        llm_fn: Funcion que llama a la API de IA
        fallback_msg: Mensaje por defecto si el circuito esta abierto
    
    Returns:
        Resultado de la funcion o mensaje de fallback
    """
    return _ia_circuit_breaker.call(llm_fn, fallback=fallback_msg)


def reset_circuit_breaker():
    """Reinicia manualmente el Circuit Breaker."""
    _ia_circuit_breaker.failure_count = 0
    _ia_circuit_breaker.state = CircuitBreaker.STATE_CLOSED
    log_event("circuit_breaker", "reset: circuito reiniciado manualmente")


def get_circuit_state() -> Dict[str, Any]:
    """Retorna el estado actual del Circuit Breaker para monitoreo."""
    return {
        "state": _ia_circuit_breaker.state,
        "failures": _ia_circuit_breaker.failure_count,
        "threshold": _ia_circuit_breaker.failure_threshold,
        "recovery_timeout": _ia_circuit_breaker.recovery_timeout,
        "remaining_cooldown": max(0.0, _ia_circuit_breaker.recovery_timeout - (time.monotonic() - _ia_circuit_breaker.last_failure_time)) if _ia_circuit_breaker.state == CircuitBreaker.STATE_OPEN else 0.0,
    }
