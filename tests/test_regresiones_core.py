from datetime import datetime
from io import BytesIO

from core import clinical_exports
from core.utils import (
    ARG_TZ,
    construir_registro_auditoria_legal,
    decodificar_base64_seguro,
    generar_hash_password,
    limite_archivo_mb,
    modo_celular_viejo_activo,
    normalizar_usuario_sistema,
    obtener_modulos_permitidos,
    preparar_imagen_clinica_bytes,
    rol_ve_datos_todas_las_clinicas,
    validar_archivo_bytes,
    validar_password_guardado,
    valor_por_modo_liviano,
)
from PIL import Image


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


def test_menu_operativo_perfil_asistencial_no_hereda_modulos_gestion():
    menu = obtener_modulos_permitidos(
        "Operativo",
        ["Visitas y Agenda", "Recetas", "Caja", "Dashboard"],
        {"rol": "Operativo", "perfil_profesional": "Operativo"},
    )

    assert "Visitas y Agenda" in menu
    assert "Recetas" in menu
    assert "Caja" not in menu
    assert "Dashboard" not in menu


def test_multiclinica_solo_para_roles_globales():
    assert rol_ve_datos_todas_las_clinicas("SuperAdmin") is True
    assert rol_ve_datos_todas_las_clinicas("Operativo") is False
    assert rol_ve_datos_todas_las_clinicas("Coordinador") is False


def test_normalizar_usuario_migra_administrativo_a_operativo():
    u = normalizar_usuario_sistema({"rol": "Administrativo", "perfil_profesional": "Administrativo"})
    assert u["rol"] == "Operativo"


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


def test_validar_archivo_bytes_aplica_limite_pdf_liviano():
    session_state = {"modo_celular_viejo": True}
    limite_mb = limite_archivo_mb("pdf", session_state)
    pdf_grande = b"x" * ((limite_mb * 1024 * 1024) + 1)

    ok, error = validar_archivo_bytes(pdf_grande, tipo="pdf", nombre_archivo="archivo.pdf", session_state=session_state)

    assert ok is False
    assert str(limite_mb) in error


def test_preparar_imagen_clinica_bytes_optimiza_y_devuelve_jpg():
    img = Image.new("RGB", (1800, 1200), color=(120, 180, 200))
    buf = BytesIO()
    img.save(buf, format="PNG")

    preparado = preparar_imagen_clinica_bytes(buf.getvalue(), nombre_archivo="foto.png")

    assert preparado["ok"] is True
    assert preparado["extension"] == "jpg"
    assert preparado["mime"] == "image/jpeg"
    assert preparado["size_bytes"] > 0


def test_decodificar_base64_seguro_no_explota_con_payload_invalido():
    assert decodificar_base64_seguro("esto-no-es-base64") == b""


def test_completar_claves_db_session_no_sobrescribe_datos_existentes(monkeypatch):
    import streamlit as st
    from core.database import completar_claves_db_session

    fake_state = {"pacientes_db": [{"id": "p1", "nombre": "Demo"}], "u_actual": {"nombre": "x"}}
    monkeypatch.setattr(st, "session_state", fake_state)
    completar_claves_db_session()
    assert fake_state["pacientes_db"] == [{"id": "p1", "nombre": "Demo"}]
    assert "administracion_med_db" in fake_state
    assert fake_state["administracion_med_db"] == []
    assert "auditoria_legal_db" in fake_state


def test_completar_claves_db_session_repara_tipos_invalidos(monkeypatch):
    import streamlit as st
    from core.database import completar_claves_db_session

    fake_state = {
        "usuarios_db": None,
        "pacientes_db": "no-es-lista",
        "detalles_pacientes_db": [],
        "u_actual": {"nombre": "x"},
    }
    monkeypatch.setattr(st, "session_state", fake_state)
    completar_claves_db_session()
    assert isinstance(fake_state["usuarios_db"], dict)
    assert fake_state["pacientes_db"] == []
    assert isinstance(fake_state["detalles_pacientes_db"], dict)


def test_normalizar_blob_datos():
    from core.database import _normalizar_blob_datos

    assert _normalizar_blob_datos(None) is None
    assert _normalizar_blob_datos({"a": 1}) == {"a": 1}
    assert _normalizar_blob_datos('{"x": 2}') == {"x": 2}
    assert _normalizar_blob_datos("[]") is None
    assert _normalizar_blob_datos([1, 2]) is None
