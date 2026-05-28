"""Tests para core._exports_pdf_base."""
from __future__ import annotations

import pytest


class TestExportsPdfBase:
    """Tests para funciones públicas de core._exports_pdf_base."""

    def test__exports_pdf_base_importable(self):
        import core._exports_pdf_base
        assert core._exports_pdf_base is not None

    def test_functions_exist(self):
        import core._exports_pdf_base
        assert callable(core._exports_pdf_base.insert_logo)
        assert callable(core._exports_pdf_base.pdf_header_oscuro)
        assert callable(core._exports_pdf_base.section_title)
        assert callable(core._exports_pdf_base.usable_width)
        assert callable(core._exports_pdf_base.write_multiline_text)
        assert callable(core._exports_pdf_base.write_pairs)
        assert callable(core._exports_pdf_base.backup_label_key)
        assert callable(core._exports_pdf_base.backup_sort_key_record)
        assert callable(core._exports_pdf_base.backup_sorted_records)
        assert callable(core._exports_pdf_base.backup_latest_record)
