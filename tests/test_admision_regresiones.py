import streamlit as st

from core import utils
from views import admision


def test_normalizar_dni_y_paciente_id_limpian_espacios():
    assert admision._normalizar_dni(" 12.345.678 ") == "12345678"
    assert admision._paciente_id("  Ana   Gomez ", " 12.345.678 ") == "Ana Gomez - 12345678"


def test_validar_legajo_requiere_empresa(monkeypatch):
    monkeypatch.setattr(admision, "_existe_dni_en_legajos", lambda *args, **kwargs: False)

    campos, error = admision._validar_legajo("Ana Gomez", "12345678", "   ", "Clinica Demo", "Admin")

    assert campos["empresa"] == ""
    assert error == "La clinica / empresa es obligatoria."


def test_validar_legajo_rechaza_dni_duplicado(monkeypatch):
    monkeypatch.setattr(admision, "_existe_dni_en_legajos", lambda *args, **kwargs: True)

    _campos, error = admision._validar_legajo("Ana Gomez", "12345678", "Clinica Demo", "Clinica Demo", "Admin")

    assert error == "Ya existe otro paciente con ese DNI."


def test_busqueda_coincidencias_legajo_considera_dni_normalizado(monkeypatch):
    pacientes = [
        {
            "id": "Ana Gomez - 12345678",
            "nombre": "Ana Gomez",
            "dni": "12345678",
            "empresa": "Clinica Demo",
            "obra_social": "OSDE",
            "estado": "Activo",
            "telefono": "",
            "direccion": "",
        }
    ]

    def fake_listar(_empresa, _rol, busqueda="", incluir_altas=False, empresa_filtro=""):
        if busqueda:
            return []
        return pacientes

    monkeypatch.setattr(admision, "_listar_pacientes_gestion", fake_listar)

    out = admision._buscar_coincidencias_legajo("12.345.678", "Clinica Demo", "Admin")

    assert len(out) == 1
    assert out[0]["dni"] == "12345678"


def test_obtener_pacientes_visibles_fusiona_sql_y_local(monkeypatch):
    fake_state = {
        "pacientes_db": ["Local Uno - 222"],
        "detalles_pacientes_db": {
            "Local Uno - 222": {
                "dni": "222",
                "empresa": "Clinica Demo",
                "estado": "Activo",
                "obra_social": "PAMI",
            }
        },
        "_ultimo_guardado_ts": 0,
    }

    monkeypatch.setattr("core.nextgen_sync._obtener_uuid_empresa", lambda empresa: "emp-1")
    monkeypatch.setattr(
        "core.db_sql.get_pacientes_by_empresa",
        lambda empresa_id, busqueda="", incluir_altas=False: [
            {
                "nombre_completo": "Sql Uno",
                "dni": "111",
                "estado": "Activo",
                "obra_social": "OSDE",
            }
        ],
    )

    visibles = utils.obtener_pacientes_visibles(fake_state, "Clinica Demo", "Admin")

    ids = {item[0] for item in visibles}
    assert "Sql Uno - 111" in ids
    assert "Local Uno - 222" in ids


def test_obtener_pacientes_visibles_registra_fallback_sql(monkeypatch):
    fake_state = {
        "pacientes_db": ["Local Uno - 222"],
        "detalles_pacientes_db": {
            "Local Uno - 222": {
                "dni": "222",
                "empresa": "Clinica Demo",
                "estado": "Activo",
                "obra_social": "PAMI",
            }
        },
        "_ultimo_guardado_ts": 0,
    }

    monkeypatch.setattr("core.nextgen_sync._obtener_uuid_empresa", lambda empresa: "emp-1")

    def falla_sql(*_args, **_kwargs):
        raise RuntimeError("conexion temporalmente no disponible")

    monkeypatch.setattr("core.db_sql.get_pacientes_by_empresa", falla_sql)

    visibles = utils.obtener_pacientes_visibles(fake_state, "Clinica Demo", "Admin")

    assert [item[0] for item in visibles] == ["Local Uno - 222"]
    status = utils.estado_pacientes_sql(fake_state)
    assert status["ok"] is False
    assert status["fallback"] == "local"
    assert status["error_type"] == "RuntimeError"
    assert "conexion temporalmente" in status["error"]


def test_registrar_auditoria_legal_resuelve_uuid_con_dni_y_empresa(monkeypatch):
    capturado = {}

    def fake_insert_auditoria(payload):
        capturado["payload"] = payload

    def fake_empresa_uuid(nombre_empresa):
        capturado["empresa"] = nombre_empresa
        return "emp-uuid"

    def fake_paciente_uuid(dni, empresa_uuid):
        capturado["paciente_args"] = (dni, empresa_uuid)
        return "pac-uuid"

    monkeypatch.setattr(st, "session_state", {})
    monkeypatch.setattr("core.db_sql.insert_auditoria", fake_insert_auditoria)
    monkeypatch.setattr("core.nextgen_sync._obtener_uuid_empresa", fake_empresa_uuid)
    monkeypatch.setattr("core.nextgen_sync._obtener_uuid_paciente", fake_paciente_uuid)

    utils.registrar_auditoria_legal(
        tipo_evento="Admision",
        paciente="Ana Gomez - 12345678",
        accion="Alta de paciente",
        actor="Recepcion",
        detalle="Alta inicial",
        empresa="Clinica Demo",
    )

    assert capturado["empresa"] == "Clinica Demo"
    assert capturado["paciente_args"] == ("12345678", "emp-uuid")
    assert capturado["payload"]["paciente_id"] == "pac-uuid"
