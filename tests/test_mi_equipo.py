"""Tests para views.mi_equipo."""
from __future__ import annotations

import pytest


class TestMiEquipo:
    """Tests para funciones públicas de views.mi_equipo."""

    def test_mi_equipo_importable(self):
        import views.mi_equipo
        assert views.mi_equipo is not None

    def test_functions_exist(self):
        import views.mi_equipo
        assert callable(views.mi_equipo.render_mi_equipo)
