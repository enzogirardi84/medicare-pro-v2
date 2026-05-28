"""Tests para core.auth_security."""
from __future__ import annotations

import pytest


class TestAuthSecurity:
    """Tests para funciones públicas de core.auth_security."""

    def test_auth_security_importable(self):
        import core.auth_security
        assert core.auth_security is not None

    def test_functions_exist(self):
        import core.auth_security
        assert callable(core.auth_security.max_login_attempts)
        assert callable(core.auth_security.lockout_segundos)
        assert callable(core.auth_security.proteccion_login_habilitada)
        assert callable(core.auth_security.lockout_persist_mode)
        assert callable(core.auth_security.puede_intentar_login)
        assert callable(core.auth_security.registrar_fallo_login)
        assert callable(core.auth_security.aplicar_jitter_tras_fallo_credenciales)
        assert callable(core.auth_security.limpiar_fallos_login)
        assert callable(core.auth_security.texto_ayuda_proteccion)
