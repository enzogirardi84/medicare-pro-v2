"""Tests para views._tareas_panel."""
from __future__ import annotations

import pytest


class TestTareasPanel:
    """Tests para funciones públicas de views._tareas_panel."""

    def test__tareas_panel_importable(self):
        import views._tareas_panel
        assert views._tareas_panel is not None

    def test_functions_exist(self):
        import views._tareas_panel
        assert callable(views._tareas_panel.render_tareas_panel)
