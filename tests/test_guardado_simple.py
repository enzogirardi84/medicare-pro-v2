"""Tests para core.guardado_simple."""
from __future__ import annotations

import pytest


class TestGuardadoSimple:
    """Tests para funciones públicas de core.guardado_simple."""

    def test_guardado_simple_importable(self):
        import core.guardado_simple
        assert core.guardado_simple is not None

    def test_functions_exist(self):
        import core.guardado_simple
        assert callable(core.guardado_simple.guardar_historial_clinico)
        assert callable(core.guardado_simple.obtener_historial_paciente)
        assert callable(core.guardado_simple.obtener_signos_vitales_paciente)
        assert callable(core.guardado_simple.obtener_evoluciones_paciente)
        assert callable(core.guardado_simple.obtener_recetas_paciente)
        assert callable(core.guardado_simple.obtener_visitas_paciente)
        assert callable(core.guardado_simple.obtener_materiales_paciente)
