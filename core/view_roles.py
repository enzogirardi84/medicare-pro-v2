"""
Acceso por modulo (vista) alineado a la matriz de roles del documento de producto.

Roles en codigo: SuperAdmin, Admin (se normaliza a SuperAdmin al cargar), Coordinador,
Operativo (incluye la antigua cuenta Administrativo), Medico, Enfermeria, Auditoria.
Medico y Enfermeria siguen la columna Operativo en modulos clinicos.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from core.feature_flags import ALERTAS_APP_PACIENTE_VISIBLE
from core.module_catalog import ALERTAS_APP_PACIENTE_MODULO
from core.view_registry import VIEW_CONFIG_BASE

COORD = "Coordinador"
OPER = "Operativo"
MED = "Medico"
ENF = "Enfermeria"
AUD = "Auditoria"

# Columna Operativo Si, Administrador No (clinica sin backoffice financiero en esa fila)
_ROL_CLINICA: List[str] = [COORD, OPER, MED, ENF]

# Coordinador + Operativo + equipo asistencial
_ROL_TODOS: List[str] = [COORD, OPER, MED, ENF]

# Coordinador + Operativo (Dashboard, cierre, RRHH, Mi Equipo, etc.)
_ROL_COORD_OPER: List[str] = [COORD, OPER]

# Solo Coordinador (gestion de equipo; SuperAdmin hace bypass aparte)
_ROL_COORD: List[str] = [COORD]

# Inventario / stock: Operativo (antes rol Administrativo)
_ROL_SOLO_OPER: List[str] = [OPER]

# Auditoria + quienes llevan control clínico/ legal
_ROL_AUDITORIA: List[str] = [COORD, AUD]


def tiene_acceso_vista(rol_actual: Optional[str], roles_permitidos: Optional[Sequence[str]]) -> bool:
    """True si el rol puede abrir el modulo. SuperAdmin y Admin tienen bypass total."""
    r = str(rol_actual or "").strip().lower()
    if r in {"superadmin", "admin"}:
        return True
    if not roles_permitidos:
        return False
    permitidos = {str(x).strip().lower() for x in roles_permitidos if x}
    return r in permitidos


# Orden del menú = orden de registro en core.view_registry (una sola fuente de verdad)
MODULO_ORDEN_MENU: tuple[str, ...] = tuple(VIEW_CONFIG_BASE.keys())

# Una entrada por cada clave en VIEW_CONFIG_BASE / main.VIEW_CONFIG
MODULO_ROLES_PERMITIDOS: Dict[str, List[str]] = {
    "Visitas y Agenda": list(_ROL_TODOS),
    "Dashboard": list(_ROL_COORD_OPER),
    # Solo SuperAdmin / Admin (bypass en tiene_acceso_vista); lista vacia = nadie mas
    "Clinicas (panel global)": [],
    "Admision": list(_ROL_TODOS),
    "Clinica": list(_ROL_CLINICA),
    "Percentilo": list(_ROL_CLINICA),
    "Asistente Clinico": list(_ROL_CLINICA),
    "Evolucion": list(_ROL_CLINICA),
    "Estudios": list(_ROL_CLINICA),
    "Materiales": list(_ROL_TODOS),
    "Recetas": list(_ROL_CLINICA),
    "Balance": list(_ROL_CLINICA),
    "Inventario": list(_ROL_SOLO_OPER),
    "Caja": list(_ROL_COORD_OPER),
    "Emergencias y Ambulancia": list(_ROL_CLINICA),
    "Alertas app paciente": list(_ROL_CLINICA),
    "Red de Profesionales": list(_ROL_TODOS),
    "Escalas Clinicas": list(_ROL_CLINICA),
    "Historial": list(_ROL_CLINICA) + [AUD],
    "PDF": list(_ROL_TODOS) + [AUD],
    "Telemedicina": list(_ROL_CLINICA),
    "Cierre Diario": list(_ROL_COORD_OPER),
    # Coordinador + Operativo: ver equipo; bajas/suspension solo segun listas blancas en Mi equipo.
    "Mi Equipo": list(_ROL_COORD_OPER),
    "Asistencia en Vivo": list(_ROL_COORD_OPER),
    "RRHH y Fichajes": list(_ROL_COORD_OPER),
    "Proyecto y Roadmap": list(_ROL_COORD_OPER),
    "Auditoria": list(_ROL_AUDITORIA),
    "Auditoria Legal": list(_ROL_AUDITORIA),
    "Diagnosticos": [],
    "APS / Dispensario": list(_ROL_TODOS) + [AUD],
    # Nuevos modulos 2026-05-14
    "Laboratorio": list(_ROL_CLINICA),
    "Vacunacion": list(_ROL_CLINICA),
    "Estadisticas": list(_ROL_COORD_OPER),
    "Portal del Paciente": list(_ROL_TODOS),
    "Factura Electronica": list(_ROL_COORD_OPER),
    "Turnos Online": list(_ROL_TODOS),
    "Chatbot IA": list(_ROL_TODOS),
}


def modulos_menu_para_rol(rol_actual: Optional[str]) -> List[str]:
    salida: List[str] = []
    for modulo in MODULO_ORDEN_MENU:
        if modulo == ALERTAS_APP_PACIENTE_MODULO and not ALERTAS_APP_PACIENTE_VISIBLE:
            continue
        perms = MODULO_ROLES_PERMITIDOS.get(modulo, [])
        if tiene_acceso_vista(rol_actual, perms):
            salida.append(modulo)
    return salida
