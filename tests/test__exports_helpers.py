"""Tests para core._exports_helpers."""
from __future__ import annotations

import pytest


class TestExportsHelpers:
    """Tests para funciones públicas de core._exports_helpers."""

    def test__exports_helpers_importable(self):
        import core._exports_helpers
        assert core._exports_helpers is not None

    def test_functions_exist(self):
        import core._exports_helpers
        assert callable(core._exports_helpers.split_patient_visual_id)
        assert callable(core._exports_helpers.normalize_patient_name)
        assert callable(core._exports_helpers.format_sql_datetime)
        assert callable(core._exports_helpers.patient_context)
        assert callable(core._exports_helpers.record_matches_patient)
        assert callable(core._exports_helpers.local_section_records)
        assert callable(core._exports_helpers.record_fingerprint)
        assert callable(core._exports_helpers.merge_records)
        assert callable(core._exports_helpers.map_sql_user_name)
        assert callable(core._exports_helpers.sql_sections_empty)
