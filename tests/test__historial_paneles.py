"""Tests para views._historial_paneles."""
from __future__ import annotations

import pytest


class TestHistorialPaneles:
    """Tests para funciones públicas de views._historial_paneles."""

    def test__historial_paneles_importable(self):
        import views._historial_paneles
        assert views._historial_paneles is not None

    def test_functions_exist(self):
        import views._historial_paneles
        assert callable(views._historial_paneles.render_resumen_clinico)
        assert callable(views._historial_paneles.render_panorama)
        assert callable(views._historial_paneles.render_tarjetas_secciones)
        assert callable(views._historial_paneles.render_timeline)
        assert callable(views._historial_paneles.render_busqueda_global)
