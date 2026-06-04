"""Tests for views.dashboard."""
from __future__ import annotations


def test_test_dashboard_importable():
    import views.dashboard
    assert views.dashboard is not None


def test_dashboard_health_agent_patient_ids_from_mixed_records():
    from views.dashboard import _ids_pacientes_para_agente

    pacientes = [
        {"paciente": "Ana - 123"},
        {"paciente": {"nombre": "Bruno", "dni": "456"}},
        {"paciente": {"nombre_completo": "Carla"}},
        {"paciente": "Ana - 123"},
        {"paciente": ""},
        None,
    ]

    assert _ids_pacientes_para_agente(pacientes) == [
        "Ana - 123",
        "Bruno - 456",
        "Carla",
    ]
