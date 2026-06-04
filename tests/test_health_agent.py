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
