"""Plantillas HTML de correo MediCare (2FA, recuperación, etc.)."""

from core.email_templates_medicare import (
    build_email_2fa_html,
    html_password_reset_body,
    medicare_email_document,
)


def test_medicare_document_shell():
    html = medicare_email_document(
        page_title="Test",
        preheader_plain="Preheader test",
        heading_plain="Título principal",
        alert_plain="Alerta de prueba",
        body_inner_html="<p>Cuerpo</p>",
    )
    assert "<!DOCTYPE html>" in html
    assert "MediCare · Seguridad" in html
    assert "Enterprise PRO" in html
    assert "Título principal" in html
    assert "Alerta de prueba" in html
    assert "Cuerpo" in html
    assert "Correo automático de seguridad" in html


def test_2fa_html_contains_code():
    html = build_email_2fa_html("847291", 10, "")
    assert "847291" in html
    assert "Verificación en dos pasos" in html
    assert "No compartas este código" in html


def test_password_reset_body_has_token():
    inner = html_password_reset_body("Ana", "", "TOKENXYZ", 30)
    assert "Ana" in inner
    assert "TOKENXYZ" in inner
    assert "Olvidé mi contraseña" in inner
    assert "PIN" in inner


def test_password_reset_body_includes_plain_link_when_url():
    inner = html_password_reset_body("Ana", "https://app.test/?pwreset=abc", "TOK", 30)
    assert "https://app.test/?pwreset=abc" in inner
    assert "Si el botón no responde" in inner
