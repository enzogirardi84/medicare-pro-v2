"""Tests para core.landing_runner."""
from __future__ import annotations

import pytest


class TestLandingRunner:
    """Tests para funciones públicas de core.landing_runner."""

    def test_landing_runner_importable(self):
        import core.landing_runner
        assert core.landing_runner is not None

    def test_functions_exist(self):
        import core.landing_runner
        assert callable(core.landing_runner.ensure_entered_app_default)
        assert callable(core.landing_runner.obtener_logo_landing)
        assert callable(core.landing_runner.render_publicidad_y_detener)
