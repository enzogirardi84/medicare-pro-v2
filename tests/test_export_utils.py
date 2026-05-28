"""Tests para core.export_utils."""
from __future__ import annotations

import pytest


class TestExportUtils:
    """Tests para funciones públicas de core.export_utils."""

    def test_export_utils_importable(self):
        import core.export_utils
        assert core.export_utils is not None

    def test_functions_exist(self):
        import core.export_utils
        assert callable(core.export_utils.safe_text)
        assert callable(core.export_utils.pdf_output_bytes)
        assert callable(core.export_utils.sanitize_filename_component)
        assert callable(core.export_utils.dataframe_csv_bytes)
