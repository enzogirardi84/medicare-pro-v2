"""Tokens de recuperación de contraseña (firmados, sin estado en servidor)."""

from unittest.mock import MagicMock, patch


def _secrets_map():
    return {
        "PASSWORD_RESET_HMAC_SECRET": "clave-secreta-larga-para-tests-12345",
        "PASSWORD_RESET_TTL_MINUTES": 60,
        "APP_PUBLIC_URL": "https://ejemplo.app",
    }


def _mock_secrets_get(key, default=None):
    return _secrets_map().get(key, default)


@patch("core.password_reset_email.st")
def test_token_roundtrip(mock_st):
    mock_st.secrets.get = MagicMock(side_effect=_mock_secrets_get)
    from core.password_reset_email import (
        construir_url_restablecimiento,
        crear_token_restablecimiento,
        verificar_token_restablecimiento,
    )

    tok, _exp = crear_token_restablecimiento("admin", "admin", "Clínica Demo")
    ok, err, info = verificar_token_restablecimiento(tok)
    assert ok is True
    assert err == ""
    assert info["uk"] == "admin"
    assert info["u_limpio"] == "admin"
    assert info["empresa"] == "Clínica Demo"

    url = construir_url_restablecimiento(tok)
    assert url.startswith("https://ejemplo.app/?pwreset=")


@patch("core.password_reset_email.st")
def test_token_malicioso_falla(mock_st):
    mock_st.secrets.get = MagicMock(side_effect=_mock_secrets_get)
    from core.password_reset_email import verificar_token_restablecimiento

    ok, err, info = verificar_token_restablecimiento("no-es-un-token")
    assert ok is False
    assert info is None
    assert err
