"""Tests para core.anticolapso."""
from __future__ import annotations

import pytest


class TestAnticolapso:
    """Tests para funciones públicas de core.anticolapso."""

    def test_anticolapso_importable(self):
        import core.anticolapso
        assert core.anticolapso is not None

    def test_functions_exist(self):
        import core.anticolapso
        assert callable(core.anticolapso.anticolapso_por_secret)
        assert callable(core.anticolapso.anticolapso_activo)
        assert callable(core.anticolapso.limite_pacientes_sidebar)
        assert callable(core.anticolapso.aplicar_politicas_anticolapso_ui)
        assert callable(core.anticolapso.render_estabilidad_anticolapso_sidebar)
