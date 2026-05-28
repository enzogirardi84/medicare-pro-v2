"""Tests para views.diagnosticos."""
from __future__ import annotations

import pytest


class TestDiagnosticos:
    """Tests para funciones públicas de views.diagnosticos."""

    def test_diagnosticos_importable(self):
        import views.diagnosticos
        assert views.diagnosticos is not None

    def test_functions_exist(self):
        import views.diagnosticos
        assert callable(views.diagnosticos.render_diagnosticos)
