"""Tests para views._recetas_prescripcion."""
from __future__ import annotations

import pytest


class TestRecetasPrescripcion:
    """Tests para funciones públicas de views._recetas_prescripcion."""

    def test__recetas_prescripcion_importable(self):
        import views._recetas_prescripcion
        assert views._recetas_prescripcion is not None

    def test_functions_exist(self):
        import views._recetas_prescripcion
        assert callable(views._recetas_prescripcion.render_nueva_prescripcion)
