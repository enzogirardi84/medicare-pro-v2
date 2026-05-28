"""Tests para core.farmacopea."""
from __future__ import annotations

import pytest


class TestFarmacopea:
    """Tests para funciones públicas de core.farmacopea."""

    def test_farmacopea_importable(self):
        import core.farmacopea
        assert core.farmacopea is not None

    def test_functions_exist(self):
        import core.farmacopea
        assert callable(core.farmacopea.normalizar_medicamento)
        assert callable(core.farmacopea.buscar_medicamento)
        assert callable(core.farmacopea.formatear_info_medicamento)
