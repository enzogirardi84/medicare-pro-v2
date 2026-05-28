"""Tests para core.email_2fa."""
from __future__ import annotations

import pytest


class TestEmail2Fa:
    """Tests para funciones públicas de core.email_2fa."""

    def test_email_2fa_importable(self):
        import core.email_2fa
        assert core.email_2fa is not None

    def test_functions_exist(self):
        import core.email_2fa
        assert callable(core.email_2fa.login_email_2fa_enabled)
        assert callable(core.email_2fa.smtp_config_ok)
        assert callable(core.email_2fa.usuario_email_2fa_valido)
        assert callable(core.email_2fa.requiere_2fa_correo)
        assert callable(core.email_2fa.limpiar_desafio_email_2fa)
        assert callable(core.email_2fa.mascarar_email_privado)
        assert callable(core.email_2fa.enviar_correo_smtp)
        assert callable(core.email_2fa.iniciar_desafio_login)
        assert callable(core.email_2fa.reenviar_codigo_login)
        assert callable(core.email_2fa.verificar_codigo_ingresado)
