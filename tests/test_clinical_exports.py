"""Tests para core.clinical_exports."""
from __future__ import annotations

import pytest


class TestClinicalExports:
    """Tests para funciones públicas de core.clinical_exports."""

    def test_clinical_exports_importable(self):
        import core.clinical_exports
        assert core.clinical_exports is not None

    def test_functions_exist(self):
        import core.clinical_exports
        assert callable(core.clinical_exports.collect_patient_sections)
        assert callable(core.clinical_exports.build_history_pdf_bytes)
        assert callable(core.clinical_exports.build_consent_pdf_bytes)
        assert callable(core.clinical_exports.build_prescription_pdf_bytes)
        assert callable(core.clinical_exports.build_emergency_pdf_bytes)
