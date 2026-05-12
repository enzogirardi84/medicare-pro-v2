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
