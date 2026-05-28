"""Tests para views.dispensario.components._tab_panel_diario."""
from __future__ import annotations

import pytest


class TestTabPanelDiario:
    """Tests para funciones públicas de views.dispensario.components._tab_panel_diario."""

    def test__tab_panel_diario_importable(self):
        import views.dispensario.components._tab_panel_diario
        assert views.dispensario.components._tab_panel_diario is not None

    def test_functions_exist(self):
        import views.dispensario.components._tab_panel_diario
        assert callable(views.dispensario.components._tab_panel_diario.render_tab_panel_diario)
