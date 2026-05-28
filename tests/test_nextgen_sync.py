"""Tests para core.nextgen_sync."""
from __future__ import annotations

import pytest


class TestNextgenSync:
    """Tests para funciones públicas de core.nextgen_sync."""

    def test_nextgen_sync_importable(self):
        import core.nextgen_sync
        assert core.nextgen_sync is not None

    def test_functions_exist(self):
        import core.nextgen_sync
        assert callable(core.nextgen_sync.sync_paciente_to_nextgen)
        assert callable(core.nextgen_sync.sync_visita_evolucion_to_nextgen)
        assert callable(core.nextgen_sync.sync_receta_to_sql)
        assert callable(core.nextgen_sync.sync_administracion_to_sql)
