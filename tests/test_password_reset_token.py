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


@patch("core.password_reset_email.st")
def test_extraer_token_desde_url_completa(mock_st):
    mock_st.secrets.get = MagicMock(side_effect=_mock_secrets_get)
    from core.password_reset_email import (
        construir_url_restablecimiento,
        crear_token_restablecimiento,
        extraer_token_restablecimiento_desde_texto,
    )

    tok, _exp = crear_token_restablecimiento("admin", "admin", "Clinica Demo")
    url = construir_url_restablecimiento(tok)

    assert extraer_token_restablecimiento_desde_texto(url) == tok
    assert extraer_token_restablecimiento_desde_texto(tok) == tok


@patch("core.password_reset_email.log_event")
@patch("core.password_reset_email.enviar_correo_smtp", return_value=(True, ""))
@patch("core.password_reset_email.smtp_config_ok", return_value=True)
def test_correo_confirmacion_password_usa_diseno_profesional(_smtp_ok, mock_send, _log_event):
    from core.password_reset_email import enviar_correo_confirmacion_cambio_password

    ok, err = enviar_correo_confirmacion_cambio_password("usuario@ejemplo.com", "Ana Perez")

    assert ok is True
    assert err == ""
    asunto = mock_send.call_args.args[1]
    html = mock_send.call_args.args[3]
    assert "actualizada" in asunto.lower()
    assert "Ana Perez" in html
    assert "MediCare" in html
