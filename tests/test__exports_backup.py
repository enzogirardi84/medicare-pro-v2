"""Tests para core._exports_backup."""
from __future__ import annotations

import pytest


class TestExportsBackup:
    """Tests para funciones públicas de core._exports_backup."""

    def test__exports_backup_importable(self):
        import core._exports_backup
        assert core._exports_backup is not None

    def test_functions_exist(self):
        import core._exports_backup
        assert callable(core._exports_backup.build_backup_pdf_bytes)
