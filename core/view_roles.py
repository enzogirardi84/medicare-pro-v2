"""
Acceso por modulo (vista) alineado a la matriz de roles del documento de producto.

Roles en codigo: SuperAdmin, Admin (se normaliza a SuperAdmin al cargar), Coordinador,
Operativo, Medico, Enfermeria, Administrativo, Auditoria.
La columna "Administrador" del documento = Administrativo aqui.
Medico y Enfermeria siguen la columna Operativo en modulos clinicos.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

COORD = "Coordinador"
OPER = "Operativo"
MED = "Medico"
ENF = "Enfermeria"
ADM = "Administrativo"
AUD = "Auditoria"

# Columna Operativo Si, Administrador No (clinica sin backoffice financiero en esa fila)
_ROL_CLINICA: List[str] = [COORD, OPER, MED, ENF]

# Las cuatro columnas con Si
_ROL_TODOS: List[str] = [COORD, OPER, MED, ENF, ADM]

# Coordinador + Administrador (Dashboard, cierre, RRHH, asistencia, inventario no)
_ROL_COORD_ADM: List[str] = [COORD, ADM]

# Solo Coordinador (gestion de equipo; SuperAdmin hace bypass aparte)
_ROL_COORD: List[str] = [COORD]

# Solo Administrativo (Inventario / Stock en el documento)
_ROL_SOLO_ADM: List[str] = [ADM]

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


# Orden del menu (mismo criterio que el listado administrativo historico)
MODULO_ORDEN_MENU: tuple[str, ...] = (
    "Visitas y Agenda",
    "Dashboard",
    "Clinicas (panel global)",
    "Admision",
    "Clinica",
    "Enfermeria",
    "Pediatria",
    "Evolucion",
    "Estudios",
    "Materiales",
    "Recetas",
    "Balance",
    "Inventario",
    "Caja",
    "Emergencias y Ambulancia",
    "Alertas app paciente",
    "Red de Profesionales",
    "Escalas Clinicas",
    "Historial",
    "PDF",
    "Telemedicina",
    "Cierre Diario",
    "Mi Equipo",
    "Asistencia en Vivo",
    "RRHH y Fichajes",
    "Proyecto y Roadmap",
    "Auditoria",
    "Auditoria Legal",
)

# Una entrada por cada clave en main.VIEW_CONFIG
MODULO_ROLES_PERMITIDOS: Dict[str, List[str]] = {
    "Visitas y Agenda": list(_ROL_TODOS),
    "Dashboard": list(_ROL_COORD_ADM),
    # Solo SuperAdmin / Admin (bypass en tiene_acceso_vista); lista vacia = nadie mas
    "Clinicas (panel global)": [],
    "Admision": list(_ROL_TODOS),
    "Clinica": list(_ROL_CLINICA),
    "Enfermeria": list(_ROL_CLINICA),
    "Pediatria": list(_ROL_CLINICA),
    "Evolucion": list(_ROL_CLINICA),
    "Estudios": list(_ROL_CLINICA),
    "Materiales": list(_ROL_TODOS),
    "Recetas": list(_ROL_CLINICA),
    "Balance": list(_ROL_CLINICA),
    "Inventario": list(_ROL_SOLO_ADM),
    "Caja": list(_ROL_TODOS),
    "Emergencias y Ambulancia": list(_ROL_CLINICA),
    "Alertas app paciente": list(_ROL_CLINICA),
    "Red de Profesionales": list(_ROL_TODOS),
    "Escalas Clinicas": list(_ROL_CLINICA),
    "Historial": list(_ROL_CLINICA) + [AUD],
    "PDF": list(_ROL_TODOS) + [AUD],
    "Telemedicina": list(_ROL_CLINICA),
    "Cierre Diario": list(_ROL_COORD_ADM),
    # Coordinador + Administrativo: ver equipo; bajas/suspension solo segun listas blancas en Mi equipo (no Operativo).
    "Mi Equipo": list(_ROL_COORD_ADM),
    "Asistencia en Vivo": list(_ROL_COORD_ADM),
    "RRHH y Fichajes": list(_ROL_COORD_ADM),
    "Proyecto y Roadmap": list(_ROL_COORD_ADM),
    "Auditoria": list(_ROL_AUDITORIA),
    "Auditoria Legal": list(_ROL_AUDITORIA),
}


def modulos_menu_para_rol(rol_actual: Optional[str]) -> List[str]:
    salida: List[str] = []
    for modulo in MODULO_ORDEN_MENU:
        perms = MODULO_ROLES_PERMITIDOS.get(modulo)
        if perms and tiene_acceso_vista(rol_actual, perms):
            salida.append(modulo)
    return salida
