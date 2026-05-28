"""Tests para views.visitas."""
from __future__ import annotations

import pytest


class TestVisitas:
    """Tests para funciones públicas de views.visitas."""

    def test_visitas_importable(self):
        import views.visitas
        assert views.visitas is not None

    def test_functions_exist(self):
        import views.visitas
        assert callable(views.visitas.render_visitas)
