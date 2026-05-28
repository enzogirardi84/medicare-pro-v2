"""Tests para core._batch_importer."""
from __future__ import annotations

import pytest


class TestBatchImporter:
    """Tests para funciones públicas de core._batch_importer."""

    def test__batch_importer_importable(self):
        import core._batch_importer
        assert core._batch_importer is not None

    def test_functions_exist(self):
        import core._batch_importer
        assert callable(core._batch_importer.import_data)
