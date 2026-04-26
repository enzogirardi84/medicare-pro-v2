"""
Registro central de vistas Streamlit: módulo → (paquete, función) y etiquetas del menú.

Mantiene el orden de inserción del menú principal. La visibilidad de «Alertas app paciente»
depende del flag de producto (misma regla que antes en main.py).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, Tuple

from core.module_catalog import ALERTAS_APP_PACIENTE_MODULO

# (import_path, render_function_name)
VIEW_CONFIG_BASE: Dict[str, Tuple[str, str]] = {
    "Visitas y Agenda": ("views.visitas", "render_visitas"),
    "Dashboard": ("views.dashboard", "render_dashboard"),
    "Clinicas (panel global)": ("views.clinicas_panel", "render_clinicas_panel"),
    "Admision": ("views.admision", "render_admision"),
    "Clinica": ("views.clinica", "render_clinica"),
    "Pediatria": ("views.pediatria", "render_pediatria"),
    "Evolucion": ("views.evolucion", "render_evolucion"),
    "Estudios": ("views.estudios", "render_estudios"),
    "Materiales": ("views.materiales", "render_materiales"),
    "Recetas": ("views.recetas", "render_recetas"),
    "Balance": ("views.balance", "render_balance"),
    "Inventario": ("views.inventario", "render_inventario"),
    "Caja": ("views.caja", "render_caja"),
    "Emergencias y Ambulancia": ("views.emergencias", "render_emergencias"),
    ALERTAS_APP_PACIENTE_MODULO: ("views.alertas_paciente_app", "render_alertas_paciente_app"),
    "Red de Profesionales": ("views.red_profesionales", "render_red_profesionales"),
    "Escalas Clinicas": ("views.escalas_clinicas", "render_escalas_clinicas"),
    "Historial": ("views.historial", "render_historial"),
    "PDF": ("views.pdf_view", "render_pdf"),
    "Telemedicina": ("views.telemedicina", "render_telemedicina"),
    "Cierre Diario": ("views.cierre_diario", "render_cierre_diario"),
    "Mi Equipo": ("views.mi_equipo", "render_mi_equipo"),
    "Asistencia en Vivo": ("views.asistencia", "render_asistencia"),
    "RRHH y Fichajes": ("views.rrhh", "render_rrhh"),
    "Proyecto y Roadmap": ("views.project_management", "render_project_management"),
    "Auditoria": ("views.auditoria", "render_auditoria"),
    "Auditoria Legal": ("views.auditoria_legal", "render_auditoria_legal"),
    "Diagnosticos": ("views.diagnosticos", "render_diagnosticos"),
}

VIEW_NAV_LABELS_BASE: Dict[str, str] = {
    "Visitas y Agenda": "schedule Visitas",
    "Dashboard": "analytics Dashboard",
    "Clinicas (panel global)": "local_hospital Clinicas",
    "Admision": "person_add Admision",
    "Clinica": "medical_services Clinica",
    "Pediatria": "child_care Pediatria",
    "Evolucion": "edit_note Evolucion",
    "Estudios": "biotech Estudios",
    "Materiales": "inventory_2 Materiales",
    "Recetas": "medication Recetas",
    "Balance": "water_drop Balance",
    "Inventario": "warehouse Inventario",
    "Caja": "payments Caja",
    "Emergencias y Ambulancia": "emergency Emergencias",
    ALERTAS_APP_PACIENTE_MODULO: "phone_iphone Alertas",
    "Red de Profesionales": "group Red",
    "Escalas Clinicas": "bar_chart Escalas",
    "Historial": "folder_open Historial",
    "PDF": "description PDF",
    "Telemedicina": "videocam Telemedicina",
    "Cierre Diario": "calculate Cierre",
    "Mi Equipo": "groups Equipo",
    "Asistencia en Vivo": "satellite_alt Asistencia",
    "RRHH y Fichajes": "timer RRHH",
    "Proyecto y Roadmap": "rocket_launch Roadmap",
    "Auditoria": "search Auditoria",
    "Auditoria Legal": "balance Legal",
    "Diagnosticos": "check_circle Diagnosticos",
}


def build_view_maps(*, alertas_app_visible: bool) -> Tuple[Dict[str, Tuple[str, str]], Dict[str, str]]:
    vc = deepcopy(VIEW_CONFIG_BASE)
    vn = deepcopy(VIEW_NAV_LABELS_BASE)
    if not alertas_app_visible:
        vc.pop(ALERTAS_APP_PACIENTE_MODULO, None)
        vn.pop(ALERTAS_APP_PACIENTE_MODULO, None)
    return vc, vn
