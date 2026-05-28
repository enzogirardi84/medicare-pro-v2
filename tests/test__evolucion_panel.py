"""Tests para views._evolucion_panel."""
from __future__ import annotations

import pytest


class TestEvolucionPanel:
    """Tests para funciones públicas de views._evolucion_panel."""

    def test__evolucion_panel_importable(self):
        import views._evolucion_panel
        assert views._evolucion_panel is not None

    def test_functions_exist(self):
        import views._evolucion_panel
        assert callable(views._evolucion_panel.get_canvas)
