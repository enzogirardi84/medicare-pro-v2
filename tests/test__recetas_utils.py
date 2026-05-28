"""Tests para views._recetas_utils."""
from __future__ import annotations

import pytest


class TestRecetasUtils:
    """Tests para funciones públicas de views._recetas_utils."""

    def test__recetas_utils_importable(self):
        import views._recetas_utils
        assert views._recetas_utils is not None

    def test_functions_exist(self):
        import views._recetas_utils
        assert callable(views._recetas_utils.render_tabla_clinica)
        assert callable(views._recetas_utils.render_dataframe_filas_tarjetas)
        assert callable(views._recetas_utils.render_plan_hidratacion_preview)
        assert callable(views._recetas_utils.archivo_a_base64)
        assert callable(views._recetas_utils.estado_icono)
        assert callable(views._recetas_utils.estado_legible)
        assert callable(views._recetas_utils.extraer_nombre_medicacion)
        assert callable(views._recetas_utils.valor_ml_h_legible)
        assert callable(views._recetas_utils.resumen_plan_hidratacion)
        assert callable(views._recetas_utils.detalle_horario_infusion)
