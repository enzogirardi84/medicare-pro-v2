"""Permisos centralizados para MediCare Enterprise PRO.

Este módulo no cambia la lógica existente por sí solo. Sirve como capa común
para que las vistas consulten permisos críticos de forma consistente.

Objetivo:
- Evitar validaciones dispersas por toda la aplicación.
- Reducir riesgo de que una acción crítica quede sin protección.
- Facilitar auditoría y mantenimiento.
"""

from __future__ import annotations

from typing import Any, Mapping


Role = str
Action = str


# Acciones críticas normalizadas.
PACIENTE_CREAR = "paciente.crear"
PACIENTE_ELIMINAR = "paciente.eliminar"
PACIENTE_EDITAR = "paciente.editar"
PACIENTE_VER_TODOS = "paciente.ver_todos"
EVOLUCION_CREAR = "evolucion.crear"
EVOLUCION_BORRAR = "evolucion.borrar"
HISTORIA_EXPORTAR = "historia.exportar"
STOCK_VER = "stock.ver"
STOCK_AJUSTAR = "stock.ajustar"
STOCK_ELIMINAR = "stock.eliminar"
FACTURACION_VER = "facturacion.ver"
FACTURACION_EDITAR = "facturacion.editar"
USUARIO_CREAR = "usuario.crear"
USUARIO_EDITAR = "usuario.editar"
CONFIGURACION_EDITAR = "configuracion.editar"
AUDITORIA_VER = "auditoria.ver"


# Matriz base. Se puede ampliar sin tocar las vistas.
_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "superadmin": {
        PACIENTE_CREAR,
        PACIENTE_ELIMINAR,
        PACIENTE_EDITAR,
        PACIENTE_VER_TODOS,
        EVOLUCION_CREAR,
        EVOLUCION_BORRAR,
        HISTORIA_EXPORTAR,
        STOCK_VER,
        STOCK_AJUSTAR,
        STOCK_ELIMINAR,
        FACTURACION_VER,
        FACTURACION_EDITAR,
        USUARIO_CREAR,
        USUARIO_EDITAR,
        CONFIGURACION_EDITAR,
        AUDITORIA_VER,
    },
    "admin": {
        PACIENTE_CREAR,
        PACIENTE_ELIMINAR,
        PACIENTE_EDITAR,
        PACIENTE_VER_TODOS,
        EVOLUCION_CREAR,
        EVOLUCION_BORRAR,
        HISTORIA_EXPORTAR,
        STOCK_VER,
        STOCK_AJUSTAR,
        STOCK_ELIMINAR,
        FACTURACION_VER,
        FACTURACION_EDITAR,
        USUARIO_CREAR,
        USUARIO_EDITAR,
        AUDITORIA_VER,
    },
    "coordinacion": {
        PACIENTE_CREAR,
        PACIENTE_EDITAR,
        PACIENTE_VER_TODOS,
        EVOLUCION_CREAR,
        HISTORIA_EXPORTAR,
        STOCK_VER,
        STOCK_AJUSTAR,
        FACTURACION_VER,
        AUDITORIA_VER,
    },
    "medico": {
        PACIENTE_EDITAR,
        EVOLUCION_CREAR,
        HISTORIA_EXPORTAR,
        STOCK_VER,
        AUDITORIA_VER,
    },
    "enfermeria": {
        EVOLUCION_CREAR,
        HISTORIA_EXPORTAR,
        STOCK_VER,
        STOCK_AJUSTAR,
    },
    "administracion": {
        PACIENTE_CREAR,
        PACIENTE_EDITAR,
        HISTORIA_EXPORTAR,
        FACTURACION_VER,
        FACTURACION_EDITAR,
        STOCK_VER,
    },
    "solo_lectura": {
        HISTORIA_EXPORTAR,
        STOCK_VER,
    },
}


_ROLE_ALIASES = {
    "super admin": "superadmin",
    "super_admin": "superadmin",
    "administrador": "admin",
    "admin_total": "admin",
    "coordinador": "coordinacion",
    "coordinación": "coordinacion",
    "médico": "medico",
    "doctor": "medico",
    "enfermero": "enfermeria",
    "enfermera": "enfermeria",
    "enfermería": "enfermeria",
    "adm": "administracion",
    "administración": "administracion",
    "recepcion": "administracion",
    "recepción": "administracion",
    "secretaria": "administracion",
    "secretaría": "administracion",
    "lectura": "solo_lectura",
}


def normalizar_rol(rol: Any) -> str:
    """Devuelve un rol normalizado y seguro."""
    value = str(rol or "").strip().lower()
    if not value:
        return "solo_lectura"
    return _ROLE_ALIASES.get(value, value)


def rol_usuario(user: Mapping[str, Any] | None) -> str:
    """Obtiene el rol desde un diccionario de usuario."""
    if not isinstance(user, Mapping):
        return "solo_lectura"
    return normalizar_rol(
        user.get("rol")
        or user.get("role")
        or user.get("perfil")
        or user.get("tipo_usuario")
    )


def es_admin(user: Mapping[str, Any] | None) -> bool:
    """True para roles con administración amplia."""
    return rol_usuario(user) in {"admin", "superadmin"}


def es_superadmin(user: Mapping[str, Any] | None) -> bool:
    """True solo para superadmin."""
    return rol_usuario(user) == "superadmin"


def puede(user: Mapping[str, Any] | None, action: Action) -> bool:
    """Valida si el usuario puede ejecutar una acción crítica.

    Ejemplo:
        if puede(st.session_state.get("u_actual"), PACIENTE_ELIMINAR):
            ...
    """
    role = rol_usuario(user)
    return action in _ROLE_PERMISSIONS.get(role, set())


def requiere_permiso(user: Mapping[str, Any] | None, action: Action) -> tuple[bool, str]:
    """Devuelve (permitido, mensaje) para usar directo en vistas."""
    if puede(user, action):
        return True, ""
    return False, "No tenés permisos suficientes para realizar esta acción."


def filtrar_acciones_permitidas(user: Mapping[str, Any] | None, actions: list[Action]) -> list[Action]:
    """Retorna solo las acciones permitidas para el usuario."""
    return [action for action in actions if puede(user, action)]
