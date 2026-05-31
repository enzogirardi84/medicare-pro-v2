"""Interceptor de acceso a datos descifrados (Access Logging).
Registra cada SELECT que descifra PHI en el audit trail inmutable.
El fallo de escritura del log ABORTA la lectura.
"""
from __future__ import annotations

import functools
import time
from typing import Any, Callable

from core.app_logging import log_event


class AccessLogInterceptor:
    """Interceptor que audita accesos a datos descifrados.

    Cada vez que un usuario solicita descifrar un campo PHI,
    se registra en el audit trail inmutable: quien, cuando,
    que paciente, que tenant. Si el log falla, la operacion
    se aborta (no se entregan datos descifrados).
    """

    @staticmethod
    def registrar_acceso(
        usuario_id: str,
        tenant_id: str,
        paciente_id: str,
        accion: str,
        tabla: str = "",
    ) -> None:
        """Registra acceso a datos descifrados en audit trail.

        Args:
            usuario_id: UUID del profesional que accede.
            tenant_id: Slug del tenant.
            paciente_id: UUID del paciente consultado.
            accion: "lectura_phi" | "descifrado_emergencia" | "exportacion".
            tabla: Tabla afectada (ej. "pacientes", "evoluciones").

        Raises:
            RuntimeError: Si falla la escritura del log.
        """
        try:
            from core.audit_trail_immutable import ImmutableAuditTrail
            auditor = ImmutableAuditTrail()
            auditor.registrar(
                usuario=usuario_id,
                accion=accion,
                recurso=f"{tabla}:{paciente_id}",
                detalle=(
                    f"Acceso a datos PHI descifrados. "
                    f"Tenant: {tenant_id}, Profesional: {usuario_id}, "
                    f"Paciente: {paciente_id}, Tabla: {tabla}"
                ),
            )
            log_event("access_log", f"ok:{usuario_id}:{paciente_id}:{accion}")
        except Exception as exc:
            log_event("access_log", f"FALLO_CRITICO:{type(exc).__name__}:{exc}")
            raise RuntimeError(
                f"No se pudo auditar el acceso a PHI. "
                f"Operacion abortada por seguridad. {exc}"
            )

    @staticmethod
    def decorate_read(
        func: Callable[..., Any]
    ) -> Callable[..., Any]:
        """Decorador para funciones que descifran datos PHI.

        Antes de ejecutar la funcion, registra el acceso.
        Si el log falla, la funcion NO se ejecuta.

        Uso:
            @AccessLogInterceptor.decorate_read
            def get_paciente(paciente_id):
                ...
        """
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            usuario_id = kwargs.get("usuario_id") or args[0] if args else ""
            paciente_id = kwargs.get("paciente_id") or args[1] if len(args) > 1 else ""
            tenant_id = kwargs.get("tenant_id") or args[2] if len(args) > 2 else ""

            AccessLogInterceptor.registrar_acceso(
                usuario_id=str(usuario_id),
                tenant_id=str(tenant_id),
                paciente_id=str(paciente_id),
                accion="lectura_phi",
                tabla=kwargs.get("tabla", ""),
            )
            return func(*args, **kwargs)
        return wrapper
