"""Tests para views/admision.py y submodulos."""
from __future__ import annotations


def test_render_admision_importable():
    from views.admision import render_admision
    assert callable(render_admision)


def test_admision_utils_importable():
    from views._admision_utils import (
        _normalizar_dni, _existe_dni_en_legajos,
        _listar_pacientes_gestion, _paciente_id,
    )
    assert callable(_normalizar_dni)
    assert callable(_paciente_id)


def test_normalizar_dni_quita_puntos_y_guiones():
    from views._admision_utils import _normalizar_dni
    resultado = _normalizar_dni("12.345.678")
    assert isinstance(resultado, str)
    assert "." not in resultado
    assert "-" not in resultado


def test_paciente_id_visual():
    from views._admision_utils import _paciente_id
    pid = _paciente_id("Juan Perez", "12345678")
    assert isinstance(pid, str)
    assert "Juan" in pid
