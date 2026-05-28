"""Tests para views.dispensario.components._helpers."""
from __future__ import annotations

import pytest


class TestHelpers:
    """Tests para funciones públicas de views.dispensario.components._helpers."""

    def test__helpers_importable(self):
        import views.dispensario.components._helpers
        assert views.dispensario.components._helpers is not None

    def test_functions_exist(self):
        import views.dispensario.components._helpers
        assert callable(views.dispensario.components._helpers.get_paciente_id_visual)
        assert callable(views.dispensario.components._helpers.input_paciente_volatil)
        assert callable(views.dispensario.components._helpers.header_paciente)
        assert callable(views.dispensario.components._helpers.guardar_con_feedback)
        assert callable(views.dispensario.components._helpers.guardar_directo)
        assert callable(views.dispensario.components._helpers.buscar_pacientes_por_texto)
        assert callable(views.dispensario.components._helpers.calcular_edad)
        assert callable(views.dispensario.components._helpers.ya_entrego_mes)
        assert callable(views.dispensario.components._helpers.calcular_edad_gestacional)
        assert callable(views.dispensario.components._helpers.paciente_info_para_selector)
