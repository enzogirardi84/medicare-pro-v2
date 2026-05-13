"""Textos de politica de contrasena (UI)."""

import unicodedata
from unittest.mock import MagicMock, patch


@patch("streamlit.secrets")
def test_texto_ayuda_politica_incluye_minimo_y_opcional_letra_numero(mock_secrets):
    def _get(k, default=None):
        m = {"PASSWORD_MIN_LENGTH": 10, "PASSWORD_REQUIRE_LETTER_AND_DIGIT": True}
        return m.get(k, default)

    mock_secrets.get = MagicMock(side_effect=_get)
    from core.password_crypto import texto_ayuda_politica_password_breve

    t = texto_ayuda_politica_password_breve()
    normalized = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    assert "10" in t
    assert "letra" in t.lower()
    assert "numero" in normalized.lower()


def test_establecer_password_nuevo_no_guarda_texto_plano():
    from core.password_crypto import establecer_password_nuevo

    usuario = {}
    establecer_password_nuevo(usuario, "ClaveSegura123")

    assert usuario["pass"] == ""
    assert usuario["pass_hash"].startswith(("$2a$", "$2b$", "$2y$"))


def test_password_legacy_texto_plano_bloqueado_por_defecto_en_produccion(monkeypatch):
    from core.password_crypto import password_usuario_coincide

    monkeypatch.setenv("MEDICARE_ENV", "production")
    monkeypatch.delenv("ALLOW_LEGACY_PLAINTEXT_PASSWORD_LOGIN", raising=False)

    ok, migrar = password_usuario_coincide({"pass": "ClaveVieja123"}, "ClaveVieja123")

    assert ok is False
    assert migrar is False


def test_password_legacy_texto_plano_solo_en_ventana_de_migracion(monkeypatch):
    from core.password_crypto import password_usuario_coincide

    monkeypatch.setenv("MEDICARE_ENV", "production")
    monkeypatch.setenv("ALLOW_LEGACY_PLAINTEXT_PASSWORD_LOGIN", "true")

    ok, migrar = password_usuario_coincide({"pass": "ClaveVieja123"}, "ClaveVieja123")

    assert ok is True
    assert isinstance(migrar, bool)
