"""
Catálogo de módulos de la app (áreas del menú lateral).

Agrupa vistas por dominio operativo (Clínica, Gestión, etc.). El mapa módulo → código
de pantalla vive en ``core.view_registry``; acá solo categorías y el nombre del
módulo de alertas paciente (flag de producto).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List

# Mismo identificador que en main.VIEW_CONFIG y core.feature_flags.
ALERTAS_APP_PACIENTE_MODULO = "Alertas app paciente"

_CATEGORIAS_BASE: Dict[str, List[str]] = {
    "Clínica": [
        "Visitas y Agenda",
        "Clinica",
        "Evolucion",
        "Estudios",
        "Recetas",
        "Balance",
        "Escalas Clinicas",
        "Historial",
        "Percentilo",
        "Telemedicina",
    ],
    "Gestión": [
        "Dashboard",
        "Admision",
        "Inventario",
        "Materiales",
        "Cierre Diario",
        "Caja",
        "RRHH y Fichajes",
        "Clinicas (panel global)",
    ],
    "Emergencias": [
        "Emergencias y Ambulancia",
        ALERTAS_APP_PACIENTE_MODULO,
        "Asistencia en Vivo",
        "Red de Profesionales",
    ],
    "Legal y documentación": [
        "PDF",
        "Auditoria",
        "Auditoria Legal",
        "Proyecto y Roadmap",
        "Mi Equipo",
    ],
}


def categorias_navegacion_sidebar(*, alertas_app_visible: bool) -> Dict[str, List[str]]:
    """
    Copia mutable del mapa categoría → módulos, alineado a VIEW_CONFIG.
    Si el flag de alertas está apagado, se quita el ítem de Emergencias.
    """
    cats = deepcopy(_CATEGORIAS_BASE)
    if not alertas_app_visible:
        try:
            cats["Emergencias"].remove(ALERTAS_APP_PACIENTE_MODULO)
        except (KeyError, ValueError):
            pass  # Intencional: item no existe o ya fue removido
    return cats
