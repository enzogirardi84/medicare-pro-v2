"""Tests para core.atajos_teclado."""
from __future__ import annotations

import pytest


class TestAtajosTeclado:
    """Tests para funciones públicas de core.atajos_teclado."""

    def test_atajos_teclado_importable(self):
        import core.atajos_teclado
        assert core.atajos_teclado is not None

    def test_functions_exist(self):
        import core.atajos_teclado
        assert callable(core.atajos_teclado.inject_atajos_teclado)
        assert callable(core.atajos_teclado.render_ayuda_atajos)
