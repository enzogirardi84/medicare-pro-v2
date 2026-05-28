"""Tests para views.dispensario.components._tabs."""
from __future__ import annotations

import pytest


class TestTabs:
    """Tests para funciones públicas de views.dispensario.components._tabs."""

    def test__tabs_importable(self):
        import views.dispensario.components._tabs
        assert views.dispensario.components._tabs is not None

    def test_functions_exist(self):
        import views.dispensario.components._tabs
        assert callable(views.dispensario.components._tabs.tab_panel_diario)
        assert callable(views.dispensario.components._tabs.tab_pacientes_familia)
        assert callable(views.dispensario.components._tabs.tab_ficha_aps)
        assert callable(views.dispensario.components._tabs.tab_turnos)
        assert callable(views.dispensario.components._tabs.tab_historial_aps)
        assert callable(views.dispensario.components._tabs.tab_nueva_atencion)
        assert callable(views.dispensario.components._tabs.tab_control_nino_embarazo)
        assert callable(views.dispensario.components._tabs.tab_farmacia)
        assert callable(views.dispensario.components._tabs.tab_trabajo_social)
        assert callable(views.dispensario.components._tabs.tab_epidemiologia)
