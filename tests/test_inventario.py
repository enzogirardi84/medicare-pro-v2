"""Tests para views.inventario."""
from __future__ import annotations

import pytest


class TestInventario:
    """Tests para funciones públicas de views.inventario."""

    def test_inventario_importable(self):
        import views.inventario
        assert views.inventario is not None

    def test_functions_exist(self):
        import views.inventario
        assert callable(views.inventario.render_inventario)
        assert callable(views.inventario.colorear_stock)
