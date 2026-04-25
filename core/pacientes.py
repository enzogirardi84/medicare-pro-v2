"""
Operaciones CRUD de pacientes y búsqueda/historial.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.input_validation import validar_dni


def registrar_auditoria(accion: str, usuario: str, detalles: dict = None):
    """Stub de auditoría; usado en tests con patch."""
    pass


def alta_paciente(session_state: dict, datos: dict) -> dict:
    """Registra un nuevo paciente en session_state."""
    dni = str(datos.get("dni", "")).strip()
    if not validar_dni(dni):
        return {"success": False, "error": "DNI inválido"}

    nombre = (datos.get("nombre") or "").strip()
    if not nombre:
        return {"success": False, "error": "El nombre es obligatorio"}

    pacientes_db = session_state.setdefault("pacientes_db", {})
    if dni in pacientes_db:
        return {"success": False, "error": f"Paciente con DNI {dni} ya existe"}

    display = f"{datos.get('apellido', '')}, {nombre} - {dni}"
    pacientes_db[dni] = display

    detalles = session_state.setdefault("detalles_pacientes_db", {})
    detalles[dni] = {
        "nombre": nombre,
        "apellido": datos.get("apellido", ""),
        "dni": dni,
        "fecha_nacimiento": datos.get("fecha_nacimiento", ""),
        "sexo": datos.get("sexo", ""),
        "telefono": datos.get("telefono", ""),
        "email": datos.get("email", ""),
        "direccion": datos.get("direccion", ""),
        "obra_social": datos.get("obra_social", ""),
        "fecha_alta": datetime.now(timezone.utc).isoformat(),
        "empresa": session_state.get("mi_empresa", ""),
    }

    user = session_state.get("u_actual", {})
    registrar_auditoria("alta_paciente", user.get("nombre", "sistema"), detalles={"dni": dni})

    return {"success": True, "paciente_id": dni}


def buscar_paciente(pacientes_db: dict, query: str) -> List[str]:
    """Busca pacientes por DNI, nombre o apellido (case-insensitive, sin tildes)."""
    import unicodedata

    def _normalize(s: str) -> str:
        return ''.join(c for c in unicodedata.normalize('NFD', s)
                       if unicodedata.category(c) != 'Mn').lower()

    q = _normalize(query or "")
    if not q:
        return []
    resultados = []
    for dni, display in pacientes_db.items():
        if q in _normalize(display):
            resultados.append(display)
    return resultados


def actualizar_paciente(session_state: dict, dni: str, nuevos_datos: dict) -> dict:
    """Actualiza datos de un paciente existente."""
    detalles = session_state.get("detalles_pacientes_db", {})
    if dni not in detalles:
        return {"success": False, "error": "Paciente no existe"}

    detalles[dni].update(nuevos_datos)

    # Actualizar display si cambió nombre/apellido
    pacientes_db = session_state.get("pacientes_db", {})
    if dni in pacientes_db:
        p = detalles[dni]
        pacientes_db[dni] = f"{p.get('apellido', '')}, {p.get('nombre', '')} - {dni}"

    user = session_state.get("u_actual", {})
    registrar_auditoria("actualizar_paciente", user.get("nombre", "sistema"), detalles={"dni": dni})

    return {"success": True}


def obtener_historial(session_state: dict, paciente_id: str) -> dict:
    """Obtiene evoluciones y vitales de un paciente, ordenadas por fecha descendente."""
    evoluciones = [
        e for e in session_state.get("evoluciones_db", [])
        if e.get("paciente_id") == paciente_id
    ]
    vitales = [
        v for v in session_state.get("vitales_db", [])
        if v.get("paciente_id") == paciente_id
    ]

    def _fecha(item):
        return item.get("fecha", "")

    evoluciones = sorted(evoluciones, key=_fecha, reverse=True)
    vitales = sorted(vitales, key=_fecha, reverse=True)

    return {"evoluciones": evoluciones, "vitales": vitales}
