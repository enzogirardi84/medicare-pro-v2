"""Tests para core._insumos_map."""
from __future__ import annotations

import pytest


class TestInsumosMap:
    """Tests para funciones públicas de core._insumos_map."""

    def test__insumos_map_importable(self):
        import core._insumos_map
        assert core._insumos_map is not None

    def test_functions_exist(self):
        import core._insumos_map
        assert callable(core._insumos_map.insumos_para_medicamento)
        assert callable(core._insumos_map.insumos_para_procedimiento)
        assert callable(core._insumos_map.deducir_insumos)
        assert callable(core._insumos_map.stock_minimo_sugerido)
        assert callable(core._insumos_map.auto_facturar_servicio)
        assert callable(core._insumos_map.sugerencias_reposicion)
