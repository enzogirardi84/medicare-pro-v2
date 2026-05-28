"""Tests para core.seguridad_extendida."""
from __future__ import annotations

import pytest


class TestSeguridadExtendida:
    """Tests para funciones públicas de core.seguridad_extendida."""

    def test_seguridad_extendida_importable(self):
        import core.seguridad_extendida
        assert core.seguridad_extendida is not None

    def test_functions_exist(self):
        import core.seguridad_extendida
        assert callable(core.seguridad_extendida.verificar_https)
        assert callable(core.seguridad_extendida.generar_csrf_token)
        assert callable(core.seguridad_extendida.verificar_csrf_token)
        assert callable(core.seguridad_extendida.inject_csrf_form)
        assert callable(core.seguridad_extendida.registrar_acceso)
        assert callable(core.seguridad_extendida.render_logs_acceso)
