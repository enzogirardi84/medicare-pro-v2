"""Tests para views.materiales."""
from __future__ import annotations

import pytest


class TestMateriales:
    """Tests para funciones públicas de views.materiales."""

    def test_materiales_importable(self):
        import views.materiales
        assert views.materiales is not None

    def test_functions_exist(self):
        import views.materiales
        assert callable(views.materiales.render_materiales)
