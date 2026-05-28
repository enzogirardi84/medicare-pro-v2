"""Tests para core.utils_pacientes."""
from __future__ import annotations

import pytest


class TestUtilsPacientes:
    """Tests para funciones públicas de core.utils_pacientes."""

    def test_utils_pacientes_importable(self):
        import core.utils_pacientes
        assert core.utils_pacientes is not None

    def test_functions_exist(self):
        import core.utils_pacientes
        assert callable(core.utils_pacientes.mapa_detalles_pacientes)
        assert callable(core.utils_pacientes.asegurar_detalles_pacientes_en_sesion)
        assert callable(core.utils_pacientes.registrar_estado_pacientes_sql)
        assert callable(core.utils_pacientes.estado_pacientes_sql)
        assert callable(core.utils_pacientes.limpiar_estado_ui_paciente)
        assert callable(core.utils_pacientes.set_paciente_actual)
        assert callable(core.utils_pacientes.obtener_pacientes_visibles)
        assert callable(core.utils_pacientes.obtener_alertas_clinicas)
        assert callable(core.utils_pacientes.obtener_profesionales_visibles)
