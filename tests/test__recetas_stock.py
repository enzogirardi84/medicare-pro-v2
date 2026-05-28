"""Tests para views._recetas_stock."""
from __future__ import annotations

import pytest


class TestRecetasStock:
    """Tests para funciones públicas de views._recetas_stock."""

    def test__recetas_stock_importable(self):
        import views._recetas_stock
        assert views._recetas_stock is not None

    def test_functions_exist(self):
        import views._recetas_stock
        assert callable(views._recetas_stock.render_control_medicacion_stock)
