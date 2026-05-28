"""Tests para views.enfermeria."""
from __future__ import annotations

import pytest


class TestEnfermeria:
    """Tests para funciones públicas de views.enfermeria."""

    def test_enfermeria_importable(self):
        import views.enfermeria
        assert views.enfermeria is not None

    def test_functions_exist(self):
        import views.enfermeria
        assert callable(views.enfermeria.render_enfermeria)
