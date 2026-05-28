"""Tests para views.vacunacion."""
from __future__ import annotations

import pytest


class TestVacunacion:
    """Tests para funciones públicas de views.vacunacion."""

    def test_vacunacion_importable(self):
        import views.vacunacion
        assert views.vacunacion is not None

    def test_functions_exist(self):
        import views.vacunacion
        assert callable(views.vacunacion.render_vacunacion)
