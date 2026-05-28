"""Tests para core.auth."""
from __future__ import annotations

import pytest


class TestAuth:
    """Tests para funciones públicas de core.auth."""

    def test_auth_importable(self):
        import core.auth
        assert core.auth is not None

    def test_functions_exist(self):
        import core.auth
        assert callable(core.auth.render_login)
        assert callable(core.auth.verificar_clinica_sesion_activa)
        assert callable(core.auth.check_inactividad)
        assert callable(core.auth.registrar_auditoria)
        assert callable(core.auth.verificar_login)
        assert callable(core.auth.crear_sesion)
        assert callable(core.auth.cerrar_sesion)
        assert callable(core.auth.verificar_timeout_sesion)
