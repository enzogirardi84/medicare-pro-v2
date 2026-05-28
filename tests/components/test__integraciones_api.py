"""Tests para views.settings.components._integraciones_api."""
from __future__ import annotations

import pytest


class TestIntegracionesApi:
    """Tests para funciones públicas de views.settings.components._integraciones_api."""

    def test__integraciones_api_importable(self):
        import views.settings.components._integraciones_api
        assert views.settings.components._integraciones_api is not None

    def test_functions_exist(self):
        import views.settings.components._integraciones_api
        assert callable(views.settings.components._integraciones_api.render_integration_settings)
