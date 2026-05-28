"""Tests para core.landing_publicidad."""
from __future__ import annotations

import pytest


class TestLandingPublicidad:
    """Tests para funciones públicas de core.landing_publicidad."""

    def test_landing_publicidad_importable(self):
        import core.landing_publicidad
        assert core.landing_publicidad is not None

    def test_functions_exist(self):
        import core.landing_publicidad
        assert callable(core.landing_publicidad.obtener_html_landing_publicidad)
