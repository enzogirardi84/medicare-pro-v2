"""Tests para core.norm_empresa."""
from __future__ import annotations

import pytest


class TestNormEmpresa:
    """Tests para funciones públicas de core.norm_empresa."""

    def test_norm_empresa_importable(self):
        import core.norm_empresa
        assert core.norm_empresa is not None

    def test_functions_exist(self):
        import core.norm_empresa
        assert callable(core.norm_empresa.norm_empresa_key)
