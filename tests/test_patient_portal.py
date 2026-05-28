"""Tests para core.patient_portal."""
from __future__ import annotations

import pytest


class TestPatientPortal:
    """Tests para funciones públicas de core.patient_portal."""

    def test_patient_portal_importable(self):
        import core.patient_portal
        assert core.patient_portal is not None

    def test_functions_exist(self):
        import core.patient_portal
        assert callable(core.patient_portal.get_patient_portal)
        assert callable(core.patient_portal.authenticate_patient)
        assert callable(core.patient_portal.render_portal_landing)
        assert callable(core.patient_portal.render_patient_dashboard)
