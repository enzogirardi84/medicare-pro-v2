"""Tests para views.settings.components._seguridad_avanzada."""
from __future__ import annotations

import pytest


class TestSeguridadAvanzada:
    """Tests para funciones públicas de views.settings.components._seguridad_avanzada."""

    def test__seguridad_avanzada_importable(self):
        import views.settings.components._seguridad_avanzada
        assert views.settings.components._seguridad_avanzada is not None

    def test_functions_exist(self):
        import views.settings.components._seguridad_avanzada
        assert callable(views.settings.components._seguridad_avanzada.render_security_settings)
        assert callable(views.settings.components._seguridad_avanzada.render_advanced_settings)
        assert callable(views.settings.components._seguridad_avanzada.render_insumos_rules_settings)
