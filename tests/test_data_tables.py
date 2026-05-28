"""Tests para core.data_tables."""
from __future__ import annotations

import pytest


class TestDataTables:
    """Tests para funciones públicas de core.data_tables."""

    def test_data_tables_importable(self):
        import core.data_tables
        assert core.data_tables is not None

    def test_functions_exist(self):
        import core.data_tables
        assert callable(core.data_tables.export_to_excel)
        assert callable(core.data_tables.export_to_csv)
        assert callable(core.data_tables.render_export_buttons)
        assert callable(core.data_tables.create_pacientes_table)
        assert callable(core.data_tables.demo_data_tables)
        assert callable(core.data_tables.render)
