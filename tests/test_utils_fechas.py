"""Tests para core.utils_fechas."""
from __future__ import annotations

import pytest


class TestUtilsFechas:
    """Tests para funciones públicas de core.utils_fechas."""

    def test_utils_fechas_importable(self):
        import core.utils_fechas
        assert core.utils_fechas is not None

    def test_functions_exist(self):
        import core.utils_fechas
        assert callable(core.utils_fechas.ahora)
        assert callable(core.utils_fechas.parse_fecha_hora)
        assert callable(core.utils_fechas.normalizar_hora_texto)
        assert callable(core.utils_fechas.parse_agenda_datetime)
        assert callable(core.utils_fechas.calcular_estado_agenda)
        assert callable(core.utils_fechas.parse_horarios_programados)
        assert callable(core.utils_fechas.horarios_programados_desde_frecuencia)
        assert callable(core.utils_fechas.calcular_velocidad_ml_h)
        assert callable(core.utils_fechas.generar_plan_escalonado_ml_h)
        assert callable(core.utils_fechas.extraer_frecuencia_desde_indicacion)
