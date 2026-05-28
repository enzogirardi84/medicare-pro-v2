"""Tests para views.rrhh."""
from __future__ import annotations

import pytest


class TestRrhh:
    """Tests para funciones públicas de views.rrhh."""

    def test_rrhh_importable(self):
        import views.rrhh
        assert views.rrhh is not None

    def test_functions_exist(self):
        import views.rrhh
        assert callable(views.rrhh.render_rrhh)
