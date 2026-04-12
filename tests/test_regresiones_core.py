from datetime import datetime

from core import clinical_exports
from core.utils import (
    ARG_TZ,
    construir_registro_auditoria_legal,
    generar_hash_password,
    modo_celular_viejo_activo,
    normalizar_usuario_sistema,
    obtener_modulos_permitidos,
    rol_ve_datos_todas_las_clinicas,
    validar_password_guardado,
    valor_por_modo_liviano,
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


def test_auditoria_legal_construye_metadata_trazable():
    fecha_evento = ARG_TZ.localize(datetime(2026, 4, 12, 9, 45, 30))
    registro = construir_registro_auditoria_legal(
        tipo_evento="Medicacion",
        paciente="Paciente Demo",
        accion="Registro de administracion",
        actor="Ana Enfermera",
        detalle="Dipirona 1 g | Horario: 08:00 | Estado: Realizada",
        referencia="Dipirona 1 g",
        empresa="Clinica Demo",
        usuario={
            "usuario_login": "ana.enf",
            "rol": "Enfermeria",
            "perfil_profesional": "Enfermeria",
            "empresa": "Clinica Demo",
        },
        modulo="Recetas",
        criticidad="alta",
        extra={"horario_programado": "08:00"},
        fecha_evento=fecha_evento,
    )

    assert registro["modulo"] == "Recetas"
    assert registro["criticidad"] == "alta"
    assert registro["actor_login"] == "ana.enf"
    assert registro["actor_rol"] == "Enfermeria"
    assert registro["actor_perfil"] == "Enfermeria"
    assert registro["empresa"] == "Clinica Demo"
    assert registro["fecha_iso"] == "2026-04-12T09:45:30-03:00"
    assert registro["horario_programado"] == "08:00"
    assert registro["audit_id"].startswith("AUD-20260412094530-")


def test_modo_celular_viejo_y_valor_liviano():
    session_state = {"modo_celular_viejo": True}

    assert modo_celular_viejo_activo(session_state) is True
    assert valor_por_modo_liviano(80, 36, session_state) == 36
    assert valor_por_modo_liviano(80, 36, {"modo_celular_viejo": False}) == 80
