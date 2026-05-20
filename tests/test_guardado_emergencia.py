from __future__ import annotations

from core.guardado_emergencia import (
    guardar_signos_vitales_local,
    guardar_evolucion_local,
    obtener_signos_vitales_local,
    obtener_evoluciones_local,
)


def test_guardar_signos_vitales_local_signature():
    result = guardar_signos_vitales_local(
        paciente_id="p1",
        paciente_nombre="Test",
        tension_arterial="120/80",
        frecuencia_cardiaca=80,
        frecuencia_respiratoria=16,
        temperatura=36.5,
        saturacion_oxigeno=98,
        glucemia="100",
    )
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], bool)
    assert isinstance(result[1], str)


def test_guardar_evolucion_local_signature():
    result = guardar_evolucion_local(
        paciente_id="p1",
        paciente_nombre="Test",
        evolucion="Paciente estable",
    )
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], bool)
    assert isinstance(result[1], str)


def test_obtener_signos_vitales_local_returns_list():
    result = obtener_signos_vitales_local("p1")
    assert isinstance(result, list)


def test_obtener_evoluciones_local_returns_list():
    result = obtener_evoluciones_local("p1")
    assert isinstance(result, list)


def test_all_functions_are_callable():
    assert callable(guardar_signos_vitales_local)
    assert callable(guardar_evolucion_local)
    assert callable(obtener_signos_vitales_local)
    assert callable(obtener_evoluciones_local)
