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
    "Percentilo": ("views.pediatria", "render_pediatria"),
    "Asistente Clinico": ("views.asistente_clinico", "render_asistente_clinico"),
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
    "APS / Dispensario": ("views.dispensario_aps", "render_dispensario_aps"),
    # Nuevos modulos 2026-05-14
    "Vacunacion": ("views.vacunacion", "render_vacunacion"),
    "Estadisticas": ("views.estadisticas", "render_estadisticas"),
    "Factura Electronica": ("views.factura_electronica", "render_factura_electronica"),
    "Turnos Online": ("views.turnos_online", "render_turnos_online"),
    "Chatbot IA": ("views.chatbot_ia", "render_chatbot_ia"),
    "Calc. Dosis Pediatricas": ("views.calculadora_dosis", "render_calculadora_dosis"),
}

VIEW_NAV_LABELS_BASE: Dict[str, str] = {
    "Visitas y Agenda": "\U0001F4CD Visitas",
    "Dashboard": "\U0001F4CA Dashboard",
    "Clinicas (panel global)": "\U0001F3E5 Clinicas",
    "Admision": "\U0001FA7E Admision",
    "Clinica": "\U0001FA7A Clinica",
    "Percentilo": "\U0001F4CF Percentilo",
    "Asistente Clinico": "\U0001F9D1\U0001F3FB\u200D\U0001F3EB Asistente Clínico",
    "Evolucion": "\u270D\ufe0f Evolucion",
    "Estudios": "\U0001F9EA Estudios",
    "Materiales": "\U0001F4E6 Materiales",
    "Recetas": "\U0001F48A Recetas",
    "Balance": "\U0001F4A7 Balance",
    "Inventario": "\U0001F3ED Inventario",
    "Caja": "\U0001F4B5 Caja",
    "Emergencias y Ambulancia": "\U0001F691 Emergencias",
    ALERTAS_APP_PACIENTE_MODULO: "\U0001F4F1 Alertas",
    "Red de Profesionales": "\U0001F91D Red",
    "Escalas Clinicas": "\U0001F4CF Escalas",
    "Historial": "\U0001F5C2 Historial",
    "PDF": "\U0001F4C4 PDF",
    "Telemedicina": "\U0001F3A5 Telemedicina",
    "Cierre Diario": "\U0001F9EE Cierre",
    "Mi Equipo": "\U0001F465 Equipo",
    "Asistencia en Vivo": "\U0001F6F0 Asistencia",
    "RRHH y Fichajes": "\u23F1 RRHH",
    "Proyecto y Roadmap": "\U0001F6E0 Roadmap",
    "Auditoria": "\U0001F50E Auditoria",
    "Auditoria Legal": "\u2696 Legal",
    "Diagnosticos": "\u2705 Diagnosticos",
    "APS / Dispensario": "\U0001F3E5 APS / Dispensario",
    # Nuevos modulos 2026-05-14
    "Vacunacion": "Vacunacion",
    "Estadisticas": "Estadisticas",
    "Factura Electronica": "Factura Electronica",
    "Turnos Online": "Turnos Online",
    "Chatbot IA": "Chatbot IA",
    "Calc. Dosis Pediatricas": "Calc. Dosis",
}


def build_view_maps(*, alertas_app_visible: bool) -> Tuple[Dict[str, Tuple[str, str]], Dict[str, str]]:
    vc = deepcopy(VIEW_CONFIG_BASE)
    vn = deepcopy(VIEW_NAV_LABELS_BASE)
    if not alertas_app_visible:
        vc.pop(ALERTAS_APP_PACIENTE_MODULO, None)
        vn.pop(ALERTAS_APP_PACIENTE_MODULO, None)
    return vc, vn
