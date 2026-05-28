"""Tests para views.estadisticas."""
from __future__ import annotations

import pytest


class TestEstadisticas:
    """Tests para funciones públicas de views.estadisticas."""

    def test_estadisticas_importable(self):
        import views.estadisticas
        assert views.estadisticas is not None

    def test_functions_exist(self):
        import views.estadisticas
        assert callable(views.estadisticas.render_estadisticas)
