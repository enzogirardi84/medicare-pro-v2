"""Tests para core.clinical_structured_export."""
from __future__ import annotations

import pytest


class TestClinicalStructuredExport:
    """Tests para funciones públicas de core.clinical_structured_export."""

    def test_clinical_structured_export_importable(self):
        import core.clinical_structured_export
        assert core.clinical_structured_export is not None

    def test_functions_exist(self):
        import core.clinical_structured_export
        assert callable(core.clinical_structured_export.build_resumen_clinico_from_session)
        assert callable(core.clinical_structured_export.export_resumen_for_llm)
        assert callable(core.clinical_structured_export.render_export_ai_button)
        assert callable(core.clinical_structured_export.to_dict)
        assert callable(core.clinical_structured_export.to_dict)
        assert callable(core.clinical_structured_export.to_dict)
        assert callable(core.clinical_structured_export.to_dict)
        assert callable(core.clinical_structured_export.to_dict)
        assert callable(core.clinical_structured_export.to_json)
