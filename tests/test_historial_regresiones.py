import json

from core import clinical_exports


def _ctx_base(**overrides):
    ctx = {
        "nombre": "Ana Nueva",
        "dni": "123",
        "empresa": "Clinica Demo",
        "empresa_id": "emp-1",
        "paciente_uuid": None,
        "detalles": {"dni": "123", "empresa": "Clinica Demo"},
    }
    ctx.update(overrides)
    return ctx


def test_collect_patient_sections_recupera_registros_locales_por_dni(monkeypatch):
    monkeypatch.setattr(clinical_exports, "_patient_context", lambda *_: _ctx_base(paciente_uuid=None))
    monkeypatch.setattr(clinical_exports, "_collect_sql_sections", lambda *_: clinical_exports._sql_sections_empty())

    session_state = {
        "detalles_pacientes_db": {
            "Ana Nueva - 123": {"dni": "123", "empresa": "Clinica Demo"},
        },
        "evoluciones_db": [
            {
                "paciente": "Ana Vieja - 123",
                "fecha": "01/04/2026 09:00",
                "nota": "Paciente estable",
            }
        ],
    }

    secciones = clinical_exports.collect_patient_sections(session_state, "Ana Nueva - 123")

    assert len(secciones["Procedimientos y Evoluciones"]) == 1
    assert secciones["Procedimientos y Evoluciones"][0]["nota"] == "Paciente estable"


def test_collect_patient_sections_fusiona_local_y_sql(monkeypatch):
    monkeypatch.setattr(clinical_exports, "_patient_context", lambda *_: _ctx_base(paciente_uuid="pac-1"))

    def fake_sql_sections(*_args):
        sections = clinical_exports._sql_sections_empty()
        sections["Signos Vitales"] = [
            {
                "id_sql": "sv-1",
                "paciente": "Ana Nueva - 123",
                "fecha": "02/04/2026 10:00",
                "TA": "120/80",
                "FC": 78,
            }
        ]
        return sections

    monkeypatch.setattr(clinical_exports, "_collect_sql_sections", fake_sql_sections)

    session_state = {
        "detalles_pacientes_db": {
            "Ana Nueva - 123": {"dni": "123", "empresa": "Clinica Demo"},
        },
        "vitales_db": [
            {
                "paciente": "Ana Nueva - 123",
                "fecha": "01/04/2026 09:00",
                "TA": "110/70",
                "FC": 72,
            }
        ],
    }

    secciones = clinical_exports.collect_patient_sections(session_state, "Ana Nueva - 123")

    assert len(secciones["Signos Vitales"]) == 2
    assert {registro["TA"] for registro in secciones["Signos Vitales"]} == {"110/70", "120/80"}


def test_export_json_historial_incluye_datos_sql(monkeypatch):
    monkeypatch.setattr(clinical_exports, "_patient_context", lambda *_: _ctx_base(paciente_uuid="pac-1"))

    def fake_sql_sections(*_args):
        sections = clinical_exports._sql_sections_empty()
        sections["Estudios Complementarios"] = [
            {
                "id_sql": "est-1",
                "paciente": "Ana Nueva - 123",
                "fecha": "03/04/2026 11:00",
                "tipo": "Radiografia",
                "detalle": "Control pulmonar",
            }
        ]
        return sections

    monkeypatch.setattr(clinical_exports, "_collect_sql_sections", fake_sql_sections)

    session_state = {
        "detalles_pacientes_db": {
            "Ana Nueva - 123": {"dni": "123", "empresa": "Clinica Demo"},
        },
    }

    payload = clinical_exports.build_patient_json_bytes(session_state, "Ana Nueva - 123")
    exportado = json.loads(payload.decode("utf-8"))

    assert exportado["secciones"]["Estudios Complementarios"][0]["tipo"] == "Radiografia"
    assert exportado["detalles"]["dni"] == "123"
