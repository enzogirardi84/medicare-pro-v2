"""Tests para views.clinicas_panel."""
from __future__ import annotations

import pytest


class TestClinicasPanel:
    """Tests para funciones públicas de views.clinicas_panel."""

    def test_clinicas_panel_importable(self):
        import views.clinicas_panel
        assert views.clinicas_panel is not None

    def test_functions_exist(self):
        import views.clinicas_panel
        assert callable(views.clinicas_panel.render_clinicas_panel)
