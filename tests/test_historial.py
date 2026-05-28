"""Tests para views.historial."""
from __future__ import annotations

import pytest


class TestHistorial:
    """Tests para funciones públicas de views.historial."""

    def test_historial_importable(self):
        import views.historial
        assert views.historial is not None

    def test_functions_exist(self):
        import views.historial
        assert callable(views.historial.render_historial)
