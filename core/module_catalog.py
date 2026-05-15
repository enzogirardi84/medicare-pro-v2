"""
Catálogo de módulos de la app (áreas del menú lateral y sub‑grupos).

Agrupa vistas por dominio operativo (Clínica, Gestión, etc.). El mapa módulo → código
de pantalla vive en ``core.view_registry``; acá solo categorías, sub‑grupos y el nombre
del módulo de alertas paciente (flag de producto).
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
        "Asistente Clinico",
        "Telemedicina",
        "Diagnosticos",
        "APS / Dispensario",
        "Laboratorio",
        "Vacunacion",
        "Calc. Dosis Pediatricas",
        "Chatbot IA",
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
        "Estadisticas",
        "Factura Electronica",
        "Turnos Online",
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

# Sub‑grupos visuales dentro de cada categoría para reducir la sensación
# de "muchos módulos". Los nombres de sub‑grupo se muestran como headers
# livianos (st.caption) y los módulos se agrupan debajo.
_SUBGRUPOS_BASE: Dict[str, Dict[str, List[str]]] = {
    "Clínica": {
        "Atención": [
            "Visitas y Agenda", "Clinica", "Evolucion",
            "Estudios", "Recetas", "APS / Dispensario",
        ],
        "Evaluación": [
            "Escalas Clinicas", "Balance", "Percentilo",
            "Historial", "Diagnosticos",
        ],
        "Laboratorio": [
            "Laboratorio", "Vacunacion",
        ],
        "Apoyo": [
            "Asistente Clinico", "Telemedicina",
            "Calc. Dosis Pediatricas", "Chatbot IA",
        ],
    },
    "Gestión": {
        "Operaciones": [
            "Dashboard", "Admision", "Cierre Diario", "Caja",
        ],
        "Recursos": [
            "Inventario", "Materiales",
            "RRHH y Fichajes", "Clinicas (panel global)",
        ],
        "Reportes": [
            "Estadisticas", "Factura Electronica", "Turnos Online",
        ],
    },
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
            pass
    return cats


def subgrupos_por_categoria(categoria: str, *, alertas_app_visible: bool) -> Dict[str, List[str]]:
    """
    Retorna los sub‑grupos visibles de *categoria*, respetando el flag de alertas.
    """
    sg = deepcopy(_SUBGRUPOS_BASE.get(categoria, {}))
    if categoria == "Emergencias" and not alertas_app_visible:
        for group, mods in sg.items():
            sg[group] = [m for m in mods if m != ALERTAS_APP_PACIENTE_MODULO]
        # Limpiar grupos que quedaron vacíos
        sg = {k: v for k, v in sg.items() if v}
    return sg
