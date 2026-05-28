"""Tests para core.data_validation."""
from __future__ import annotations

import pytest


class TestDataValidation:
    """Tests para funciones públicas de core.data_validation."""

    def test_data_validation_importable(self):
        import core.data_validation
        assert core.data_validation is not None

    def test_functions_exist(self):
        import core.data_validation
        assert callable(core.data_validation.get_validator)
        assert callable(core.data_validation.validate_dni)
        assert callable(core.data_validation.validate_email)
        assert callable(core.data_validation.sanitize)
        assert callable(core.data_validation.validate_dni)
        assert callable(core.data_validation.validate_email)
        assert callable(core.data_validation.validate_phone)
        assert callable(core.data_validation.validate_matricula)
        assert callable(core.data_validation.validate_patient_data)
        assert callable(core.data_validation.validate_birth_date)
