"""Tests para core.sync_utils."""
from __future__ import annotations

import pytest


class TestSyncUtils:
    """Tests para funciones públicas de core.sync_utils."""

    def test_sync_utils_importable(self):
        import core.sync_utils
        assert core.sync_utils is not None

    def test_functions_exist(self):
        import core.sync_utils
        assert callable(core.sync_utils.auto_vencer_indicaciones)
        assert callable(core.sync_utils.sync_pendientes_agenda_sql)
        assert callable(core.sync_utils.sync_pendientes_consumos_sql)
        assert callable(core.sync_utils.sync_pendientes_facturacion_sql)
        assert callable(core.sync_utils.backup_diario_sql)
        assert callable(core.sync_utils.sync_todo)
