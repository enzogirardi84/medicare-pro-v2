"""Tests para core.app_mobile."""
from __future__ import annotations

import pytest


class TestAppMobile:
    """Tests para funciones públicas de core.app_mobile."""

    def test_app_mobile_importable(self):
        import core.app_mobile
        assert core.app_mobile is not None

    def test_functions_exist(self):
        import core.app_mobile
        assert callable(core.app_mobile.cliente_es_movil_probable)
        assert callable(core.app_mobile.cliente_es_tablet_probable)
        assert callable(core.app_mobile.render_patient_selector)
