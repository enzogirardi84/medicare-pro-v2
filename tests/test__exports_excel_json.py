"""Tests para core._exports_excel_json."""
from __future__ import annotations

import pytest


class TestExportsExcelJson:
    """Tests para funciones públicas de core._exports_excel_json."""

    def test__exports_excel_json_importable(self):
        import core._exports_excel_json
        assert core._exports_excel_json is not None

    def test_functions_exist(self):
        import core._exports_excel_json
        assert callable(core._exports_excel_json.build_patient_excel_bytes)
        assert callable(core._exports_excel_json.build_patient_json_bytes)
