"""Tests para core.phi_encryption."""
from __future__ import annotations

import pytest


class TestPhiEncryption:
    """Tests para funciones públicas de core.phi_encryption."""

    def test_phi_encryption_importable(self):
        import core.phi_encryption
        assert core.phi_encryption is not None

    def test_functions_exist(self):
        import core.phi_encryption
        assert callable(core.phi_encryption.get_phi_manager)
        assert callable(core.phi_encryption.encrypt_patient_data)
        assert callable(core.phi_encryption.decrypt_patient_data)
        assert callable(core.phi_encryption.encrypt_evolucion)
        assert callable(core.phi_encryption.decrypt_evolucion)
        assert callable(core.phi_encryption.is_field_encrypted)
        assert callable(core.phi_encryption.render_phi_status)
        assert callable(core.phi_encryption.encrypt_value)
        assert callable(core.phi_encryption.decrypt_value)
        assert callable(core.phi_encryption.encrypt_record)
