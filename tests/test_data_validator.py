"""Tests para core.data_validator."""
from __future__ import annotations

import pytest


class TestDataValidator:
    """Tests para funciones públicas de core.data_validator."""

    def test_data_validator_importable(self):
        import core.data_validator
        assert core.data_validator is not None

    def test_functions_exist(self):
        import core.data_validator
        assert callable(core.data_validator.get_paciente_schema)
        assert callable(core.data_validator.get_usuario_schema)
        assert callable(core.data_validator.get_validator)
        assert callable(core.data_validator.validate_paciente)
        assert callable(core.data_validator.validate_usuario)
        assert callable(core.data_validator.sanitize_string)
        assert callable(core.data_validator.register_schema)
        assert callable(core.data_validator.register_schemas)
        assert callable(core.data_validator.validate)
