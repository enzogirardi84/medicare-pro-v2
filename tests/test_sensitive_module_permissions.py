from core.utils import obtener_modulos_permitidos
from core.view_roles import MODULO_ROLES_PERMITIDOS, tiene_acceso_vista


def test_caja_no_se_expone_a_roles_clinicos_ni_auditoria():
    permisos_caja = MODULO_ROLES_PERMITIDOS["Caja"]

    assert tiene_acceso_vista("Coordinador", permisos_caja) is True
    assert tiene_acceso_vista("Operativo", permisos_caja) is True
    assert tiene_acceso_vista("Medico", permisos_caja) is False
    assert tiene_acceso_vista("Enfermeria", permisos_caja) is False
    assert tiene_acceso_vista("Auditoria", permisos_caja) is False


def test_auditoria_no_hereda_rrhh_caja_ni_mi_equipo_en_menu_legacy():
    modulos = [
        "Dashboard",
        "Caja",
        "Mi Equipo",
        "RRHH y Fichajes",
        "Auditoria Legal",
        "Historial",
        "PDF",
    ]

    menu = obtener_modulos_permitidos("Auditoria", modulos, {"rol": "Auditoria"})

    assert "Caja" not in menu
    assert "Mi Equipo" not in menu
    assert "RRHH y Fichajes" not in menu
    assert "Auditoria Legal" in menu
    assert "Historial" in menu
    assert "PDF" in menu


def test_modulos_admin_globales_siguen_solo_con_bypass():
    for modulo in ("Clinicas (panel global)", "Diagnosticos"):
        permisos = MODULO_ROLES_PERMITIDOS[modulo]
        assert tiene_acceso_vista("SuperAdmin", permisos) is True
        assert tiene_acceso_vista("Admin", permisos) is True
        assert tiene_acceso_vista("Coordinador", permisos) is False
        assert tiene_acceso_vista("Auditoria", permisos) is False
