"""Tests for core.health_agent."""

from __future__ import annotations


def test_health_agent_creates_critical_action_from_vitals():
    from core.health_agent import generar_plan_agente_salud

    datos = {
        "vitales": [
            {
                "paciente": "Ana",
                "fecha": "2026-06-03 10:00",
                "presion_arterial": "170/100",
                "saturacion_o2": 88,
            }
        ],
        "indicaciones": [],
        "cuidados": [],
        "consumos": [],
        "balance": [],
        "estudios": [],
        "administracion_med": [],
        "diagnosticos": [],
        "escalas": [],
        "emergencias": [],
        "evoluciones": [],
        "checkin": [],
        "paciente_data": {"nombre": "Ana"},
    }

    resultado = generar_plan_agente_salud("Ana", datos)

    assert resultado.estado == "critico"
    assert resultado.acciones_criticas >= 1
    assert any(a.modulo_sugerido == "Clinica" for a in resultado.acciones)


def test_health_agent_adds_minimum_records_action_when_empty():
    from core.health_agent import generar_plan_agente_salud

    datos = {
        "vitales": [],
        "indicaciones": [],
        "cuidados": [],
        "consumos": [],
        "balance": [],
        "estudios": [],
        "administracion_med": [],
        "diagnosticos": [],
        "escalas": [],
        "emergencias": [],
        "evoluciones": [],
        "checkin": [],
        "paciente_data": {},
    }

    resultado = generar_plan_agente_salud("Paciente sin datos", datos)

    assert resultado.estado == "estable"
    assert any(a.id == "cobertura-vitales" for a in resultado.acciones)
    assert any(a.id == "cobertura-evolucion" for a in resultado.acciones)


def test_health_agent_builds_shift_handoff_and_today_plan():
    from core.health_agent import generar_plan_agente_salud

    datos = {
        "vitales": [],
        "indicaciones": [],
        "cuidados": [],
        "consumos": [],
        "balance": [],
        "estudios": [{"estado": "pendiente", "tipo": "Laboratorio"}],
        "administracion_med": [],
        "diagnosticos": [],
        "escalas": [],
        "emergencias": [],
        "evoluciones": [],
        "checkin": [],
        "paciente_data": {},
    }

    resultado = generar_plan_agente_salud("Paciente", datos)

    assert "Pase de guardia" in resultado.pase_guardia
    assert "Resumen para derivacion/auditoria" in resultado.resumen_derivacion
    assert resultado.plan_hoy
    assert resultado.tareas_urgentes


def test_health_agent_registers_action_trace():
    from core.health_agent import registrar_accion_agente

    session_state = {}
    evento = registrar_accion_agente(
        session_state,
        paciente_id="Ana",
        accion_id="a1",
        accion_titulo="Controlar signos vitales",
        actor="Tester",
        estado="realizada",
        emit_audit=False,
    )

    assert evento["paciente"] == "Ana"
    assert session_state["agente_salud_acciones_log"][0]["accion_id"] == "a1"
    assert session_state["agente_salud_acciones_db"][0]["accion_id"] == "a1"


def test_health_agent_patient_audit_id_does_not_expose_patient_text():
    from core.health_agent import _patient_audit_id

    raw = "Ana Gomez - 12345678"
    audit_id = _patient_audit_id(raw)

    assert audit_id.startswith("patient:")
    assert "Ana" not in audit_id
    assert "12345678" not in audit_id
