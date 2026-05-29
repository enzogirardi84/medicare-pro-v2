"""Servicio de pacientes — reglas de negocio sin dependencias de Streamlit."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple


def calcular_edad(fecha_nacimiento: Optional[str]) -> Tuple[Optional[int], Optional[str]]:
    """Calcula edad a partir de fecha de nacimiento ISO.

    Returns:
        (edad_en_anios, etiqueta_formateada)
    """
    if not fecha_nacimiento:
        return None, None
    try:
        fn = datetime.fromisoformat(fecha_nacimiento.replace("Z", "+00:00")).date()
        hoy = date.today()
        edad = hoy.year - fn.year - ((hoy.month, hoy.day) < (fn.month, fn.day))
        return edad, f"{edad} años"
    except (ValueError, TypeError):
        return None, None


def validar_dni(dni: str) -> bool:
    """Valida formato basico de DNI argentino (7-8 digitos)."""
    dni = str(dni or "").strip().replace(".", "").replace("-", "")
    return dni.isdigit() and 7 <= len(dni) <= 8


def normalizar_telefono(tel: str) -> str:
    """Normaliza numero de telefono: solo digitos."""
    return "".join(c for c in str(tel or "") if c.isdigit())


def paciente_es_mayor_edad(fecha_nacimiento: Optional[str]) -> bool:
    """True si el paciente tiene 18+ años."""
    edad, _ = calcular_edad(fecha_nacimiento)
    return edad is not None and edad >= 18


def buscar_pacientes_por_texto(pacientes: List[Dict[str, Any]], texto: str) -> List[Dict[str, Any]]:
    """Filtra lista de pacientes por texto libre (nombre, apellido, DNI)."""
    if not texto:
        return pacientes
    texto = texto.strip().lower()
    if not texto:
        return pacientes
    resultados = []
    for p in pacientes:
        nombre = str(p.get("nombre_completo", p.get("nombre", ""))).lower()
        dni = str(p.get("dni", ""))
        if texto in nombre or texto in dni:
            resultados.append(p)
    return resultados


def mapear_detalles_paciente(paciente: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza los campos de un paciente para mostrar en UI."""
    nombre = str(paciente.get("nombre_completo") or paciente.get("nombre", "") or "")
    apellido = str(paciente.get("apellido", ""))
    nombre_completo = f"{nombre} {apellido}".strip() or "S/D"
    edad, edad_str = calcular_edad(paciente.get("fecha_nacimiento"))

    return {
        "nombre": nombre_completo,
        "dni": str(paciente.get("dni", "S/D")),
        "edad": edad,
        "edad_str": edad_str or "S/D",
        "sexo": str(paciente.get("sexo", "S/D")),
        "obra_social": str(paciente.get("obra_social", "S/D")),
        "telefono": str(paciente.get("telefono", "")),
        "direccion": str(paciente.get("direccion", "")),
        "estado": str(paciente.get("estado", "Activo")),
        "alergias": str(paciente.get("alergias", "")),
        "patologias": str(paciente.get("patologias", "") or paciente.get("diagnostico", "")),
    }
