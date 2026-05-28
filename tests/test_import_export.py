"""Tests para core.import_export."""
from __future__ import annotations

import pytest


class TestImportExport:
    """Tests para funciones públicas de core.import_export."""

    def test_import_export_importable(self):
        import core.import_export
        assert core.import_export is not None

    def test_functions_exist(self):
        import core.import_export
        assert callable(core.import_export.get_importer)
        assert callable(core.import_export.get_exporter)
        assert callable(core.import_export.export_patients_to_csv)
        assert callable(core.import_export.export_patients_to_excel)
        assert callable(core.import_export.import_patients_from_csv)
        assert callable(core.import_export.import_patients)
        assert callable(core.import_export.export_patients)
        assert callable(core.import_export.export_evoluciones)
