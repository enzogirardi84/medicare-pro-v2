"""Tests para core.guardado_universal."""
from __future__ import annotations

import pytest


class TestGuardadoUniversal:
    """Tests para funciones públicas de core.guardado_universal."""

    def test_guardado_universal_importable(self):
        import core.guardado_universal
        assert core.guardado_universal is not None

    def test_functions_exist(self):
        import core.guardado_universal
        assert callable(core.guardado_universal.guardar_registro)
        assert callable(core.guardado_universal.obtener_registros)
        assert callable(core.guardado_universal.obtener_historial_paciente)
        assert callable(core.guardado_universal.contar_registros)
        assert callable(core.guardado_universal.guardar_signos_vitales)
        assert callable(core.guardado_universal.guardar_evolucion)
        assert callable(core.guardado_universal.guardar_material)
        assert callable(core.guardado_universal.guardar_receta)
        assert callable(core.guardado_universal.obtener_signos_vitales)
        assert callable(core.guardado_universal.obtener_evoluciones)
