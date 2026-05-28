"""Tests para core.app_performance."""
from __future__ import annotations

import pytest


class TestAppPerformance:
    """Tests para funciones públicas de core.app_performance."""

    def test_app_performance_importable(self):
        import core.app_performance
        assert core.app_performance is not None

    def test_functions_exist(self):
        import core.app_performance
        assert callable(core.app_performance.procesar_guardado_pendiente_seguro)
        assert callable(core.app_performance.guardar_datos_seguro)
        assert callable(core.app_performance.render_metricas_admin_sidebar)
