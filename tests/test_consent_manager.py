"""Tests para core.consent_manager."""
from __future__ import annotations

import pytest


class TestConsentManager:
    """Tests para funciones públicas de core.consent_manager."""

    def test_consent_manager_importable(self):
        import core.consent_manager
        assert core.consent_manager is not None

    def test_functions_exist(self):
        import core.consent_manager
        assert callable(core.consent_manager.get_consent_manager)
        assert callable(core.consent_manager.calculate_hash)
        assert callable(core.consent_manager.verify_integrity)
        assert callable(core.consent_manager.to_dict)
        assert callable(core.consent_manager.get_template)
        assert callable(core.consent_manager.render_template)
        assert callable(core.consent_manager.create_consent)
        assert callable(core.consent_manager.sign_consent)
        assert callable(core.consent_manager.get_consent)
        assert callable(core.consent_manager.get_patient_consents)
