"""Tests para core.password_reset_email."""
from __future__ import annotations

import pytest


class TestPasswordResetEmail:
    """Tests para funciones públicas de core.password_reset_email."""

    def test_password_reset_email_importable(self):
        import core.password_reset_email
        assert core.password_reset_email is not None

    def test_functions_exist(self):
        import core.password_reset_email
        assert callable(core.password_reset_email.password_reset_ttl_seconds)
        assert callable(core.password_reset_email.crear_token_restablecimiento)
        assert callable(core.password_reset_email.verificar_token_restablecimiento)
        assert callable(core.password_reset_email.construir_url_restablecimiento)
        assert callable(core.password_reset_email.extraer_token_restablecimiento_desde_texto)
        assert callable(core.password_reset_email.enviar_correo_restablecimiento)
        assert callable(core.password_reset_email.enviar_correo_confirmacion_cambio_password)
