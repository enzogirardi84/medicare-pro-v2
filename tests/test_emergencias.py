"""Tests para views.emergencias."""
from __future__ import annotations

import pytest


class TestEmergencias:
    """Tests para funciones públicas de views.emergencias."""

    def test_emergencias_importable(self):
        import views.emergencias
        assert views.emergencias is not None

    def test_functions_exist(self):
        import views.emergencias
        assert callable(views.emergencias.render_emergencias)
