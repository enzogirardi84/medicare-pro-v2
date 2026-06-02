"""Función unificada de retry con exponential backoff para operaciones Supabase."""
from __future__ import annotations

import secrets
import time


def supabase_execute_with_retry(op_name: str, fn, attempts: int = 3, base_delay: float = 0.15):
    """Ejecuta fn con exponential backoff + jitter. Re-lanza si se agotan los intentos."""
    for i in range(attempts):
        try:
            return fn()
        except Exception:
            if i == attempts - 1:
                raise
            delay = base_delay * (2**i) + secrets.randbelow(100) / 1000.0
            time.sleep(delay)
    return fn()
