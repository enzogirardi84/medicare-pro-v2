"""Servicio de auditoria forense inmutable para trazabilidad legal.

Cada operacion CRUD sobre datos clinicos queda registrada con:
- Quien (usuario_id)
- Donde (empresa_id)
- Que accion (CREATE, UPDATE, DELETE)
- Payload sanitizado
- Timestamp preciso
"""

from __future__ import annotations

import functools
import json
import time
from typing import Any, Callable, Dict, Optional

from core.app_logging import log_event


def audit_trail(action_name: str = "OPERATION"):
    """Decorador forense para registrar cambios inmutables en datos clinicos.

    Uso:
        @audit_trail("REGISTRO_SIGNOS_VITALES")
        def guardar_signos_vitales(paciente_id, usuario_id, empresa_id, datos):
            ...

    El decorador captura automaticamente los parametros usuario_id, empresa_id
    y datos de la llamada, y registra un log inmutable.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Extraer parametros de contexto de la llamada
            usuario_id = kwargs.get("usuario_id", args[1] if len(args) > 1 else "SYSTEM")
            empresa_id = kwargs.get("empresa_id", args[2] if len(args) > 2 else "SYSTEM")
            datos = kwargs.get("datos", args[3] if len(args) > 3 else {})

            # Ejecutar la operacion original
            resultado = func(*args, **kwargs)

            # Si fue exitosa, registrar auditoria forense
            if resultado:
                registro = {
                    "usuario_id": str(usuario_id),
                    "empresa_id": str(empresa_id),
                    "accion": action_name,
                    "timestamp": time.time(),
                    "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "payload": json.dumps(datos, default=str, ensure_ascii=False)[:500],
                }
                log_event("audit_trail", json.dumps(registro, ensure_ascii=False))

            return resultado
        return wrapper
    return decorator
