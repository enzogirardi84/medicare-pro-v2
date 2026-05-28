"""Tests para core.password_crypto."""
from __future__ import annotations

import pytest


class TestPasswordCrypto:
    """Tests para funciones públicas de core.password_crypto."""

    def test_password_crypto_importable(self):
        import core.password_crypto
        assert core.password_crypto is not None

    def test_functions_exist(self):
        import core.password_crypto
        assert callable(core.password_crypto.hashing_disponible)
        assert callable(core.password_crypto.legacy_password_login_enabled)
        assert callable(core.password_crypto.bcrypt_rounds_config)
        assert callable(core.password_crypto.parece_hash_bcrypt)
        assert callable(core.password_crypto.hash_password)
        assert callable(core.password_crypto.verificar_password)
        assert callable(core.password_crypto.password_usuario_coincide)
        assert callable(core.password_crypto.aplicar_hash_tras_login_ok)
        assert callable(core.password_crypto.password_min_length)
        assert callable(core.password_crypto.password_exigir_letra_y_numero)
