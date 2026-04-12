from core import clinical_exports
from core.utils import (
    generar_hash_password,
    normalizar_usuario_sistema,
    obtener_modulos_permitidos,
    rol_ve_datos_todas_las_clinicas,
    validar_password_guardado,
)


def test_password_hash_y_compatibilidad_legacy():
    password = "ClaveSegura123"
    hashed = generar_hash_password(password)

    assert hashed != password
    assert validar_password_guardado(hashed, password) is True
    assert validar_password_guardado(password, password) is True
    assert validar_password_guardado(hashed, "OtraClave999") is False


def test_normalizar_usuario_recupera_rol_clinico_legacy():
    usuario = normalizar_usuario_sistema(
        {"rol": "Administrativo", "perfil_profesional": "Medico"}
    )

    assert usuario["rol"] == "Medico"
    assert usuario["perfil_profesional"] == "Medico"


def test_menu_operativo_legacy_no_hereda_modulos_administrativos():
    menu = obtener_modulos_permitidos(
        "Administrativo",
        ["Visitas y Agenda", "Recetas", "Caja", "Dashboard"],
        {"rol": "Administrativo", "perfil_profesional": "Operativo"},
    )

    assert "Visitas y Agenda" in menu
    assert "Recetas" in menu
    assert "Caja" not in menu
    assert "Dashboard" not in menu


def test_multiclinica_solo_para_roles_globales():
    assert rol_ve_datos_todas_las_clinicas("SuperAdmin") is True
    assert rol_ve_datos_todas_las_clinicas("Administrativo") is False
    assert rol_ve_datos_todas_las_clinicas("Coordinador") is False


def test_historia_pdf_degrada_bien_sin_reportlab(monkeypatch):
    monkeypatch.setattr(clinical_exports, "REPORTLAB_DISPONIBLE", False)

    payload = clinical_exports.build_history_pdf_bytes({}, "Paciente Demo", "Clinica Demo")

    assert payload is None
