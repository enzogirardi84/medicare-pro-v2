"""Tests para views._recetas_indicaciones."""
from __future__ import annotations

import pytest


class TestRecetasIndicaciones:
    """Tests para funciones públicas de views._recetas_indicaciones."""

    def test__recetas_indicaciones_importable(self):
        import views._recetas_indicaciones
        assert views._recetas_indicaciones is not None

    def test_functions_exist(self):
        import views._recetas_indicaciones
        assert callable(views._recetas_indicaciones.construir_texto_indicacion)
        assert callable(views._recetas_indicaciones.resumen_medicacion_activa)
