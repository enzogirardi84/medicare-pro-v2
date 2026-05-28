"""Tests para views.calculadora_dosis."""
from __future__ import annotations

import pytest


class TestCalculadoraDosis:
    """Tests para funciones públicas de views.calculadora_dosis."""

    def test_calculadora_dosis_importable(self):
        import views.calculadora_dosis
        assert views.calculadora_dosis is not None

    def test_functions_exist(self):
        import views.calculadora_dosis
        assert callable(views.calculadora_dosis.render_calculadora_dosis)
