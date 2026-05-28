"""Tests para views._dashboard_bloques."""
from __future__ import annotations

import pytest


class TestDashboardBloques:
    """Tests para funciones públicas de views._dashboard_bloques."""

    def test__dashboard_bloques_importable(self):
        import views._dashboard_bloques
        assert views._dashboard_bloques is not None

    def test_functions_exist(self):
        import views._dashboard_bloques
        assert callable(views._dashboard_bloques.render_notificaciones_turno)
        assert callable(views._dashboard_bloques.render_vitales_alertas)
        assert callable(views._dashboard_bloques.render_vista_operativa)
        assert callable(views._dashboard_bloques.render_listados_ejecutivos)
