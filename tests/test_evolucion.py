"""Tests para views.evolucion."""
from __future__ import annotations

import pytest


class TestEvolucion:
    """Tests para funciones públicas de views.evolucion."""

    def test_evolucion_importable(self):
        import views.evolucion
        assert views.evolucion is not None

    def test_functions_exist(self):
        import views.evolucion
        assert callable(views.evolucion.render_evolucion)
