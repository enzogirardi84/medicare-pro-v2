"""Tests para core.input_validation."""
from __future__ import annotations

import pytest


class TestInputValidation:
    """Tests para funciones públicas de core.input_validation."""

    def test_input_validation_importable(self):
        import core.input_validation
        assert core.input_validation is not None

    def test_functions_exist(self):
        import core.input_validation
        assert callable(core.input_validation.email_formato_aceptable)
        assert callable(core.input_validation.validar_dni)
        assert callable(core.input_validation.validar_telefono)
        assert callable(core.input_validation.validar_email)
        assert callable(core.input_validation.sanitizar_html)
        assert callable(core.input_validation.validar_longitud_maxima)
        assert callable(core.input_validation.sanitizar_sql)
        assert callable(core.input_validation.validar_dni_seguro)
        assert callable(core.input_validation.validar_monto)
