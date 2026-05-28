"""Tests para core.session_auth_cleanup."""
from __future__ import annotations

import pytest


class TestSessionAuthCleanup:
    """Tests para funciones públicas de core.session_auth_cleanup."""

    def test_session_auth_cleanup_importable(self):
        import core.session_auth_cleanup
        assert core.session_auth_cleanup is not None

    def test_functions_exist(self):
        import core.session_auth_cleanup
        assert callable(core.session_auth_cleanup.limpiar_estado_sesion_login_efimero)
