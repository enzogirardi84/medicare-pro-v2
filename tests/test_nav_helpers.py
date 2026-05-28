"""Tests para core.nav_helpers."""
from __future__ import annotations

import pytest


class TestNavHelpers:
    """Tests para funciones públicas de core.nav_helpers."""

    def test_nav_helpers_importable(self):
        import core.nav_helpers
        assert core.nav_helpers is not None

    def test_functions_exist(self):
        import core.nav_helpers
        assert callable(core.nav_helpers.get_categorias_modulos)
        assert callable(core.nav_helpers.get_categorias_orden)
        assert callable(core.nav_helpers.categorias_con_modulos_en_menu)
        assert callable(core.nav_helpers.etiqueta_filtro_categoria)
        assert callable(core.nav_helpers.obtener_subgrupos_categoria)
        assert callable(core.nav_helpers.modulos_en_categoria)
