"""Tests para core.app_session."""
from __future__ import annotations

import pytest


class TestAppSession:
    """Tests para funciones públicas de core.app_session."""

    def test_app_session_importable(self):
        import core.app_session
        assert core.app_session is not None

    def test_functions_exist(self):
        import core.app_session
        assert callable(core.app_session.limpiar_sesion_app)
        assert callable(core.app_session.reset_total_app)
        assert callable(core.app_session.inicializar_db_state_seguro)
        assert callable(core.app_session.eliminar_overlay_residual)
