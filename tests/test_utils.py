"""Tests para core.utils."""
from __future__ import annotations

import pytest


class TestUtils:
    """Tests para funciones públicas de core.utils."""

    def test_utils_importable(self):
        import core.utils
        assert core.utils is not None

    def test_functions_exist(self):
        import core.utils
        assert callable(core.utils.password_requiere_migracion)
        assert callable(core.utils.actualizar_password_usuario)
        assert callable(core.utils.generar_hash_password)
        assert callable(core.utils.validar_password_guardado)
        assert callable(core.utils.decodificar_base64_seguro)
        assert callable(core.utils.validar_dni)
        assert callable(core.utils.validar_email)
        assert callable(core.utils.validar_telefono)
        assert callable(core.utils.validar_texto_obligatorio)
        assert callable(core.utils.obtener_emergency_password)
