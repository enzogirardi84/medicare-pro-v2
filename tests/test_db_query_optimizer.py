"""Tests para core.db_query_optimizer."""
from __future__ import annotations

import pytest


class TestDbQueryOptimizer:
    """Tests para funciones públicas de core.db_query_optimizer."""

    def test_db_query_optimizer_importable(self):
        import core.db_query_optimizer
        assert core.db_query_optimizer is not None

    def test_functions_exist(self):
        import core.db_query_optimizer
        assert callable(core.db_query_optimizer.fetch_with_cursor)
        assert callable(core.db_query_optimizer.fetch_pacientes_optimizado)
        assert callable(core.db_query_optimizer.fetch_evoluciones_paciente)
        assert callable(core.db_query_optimizer.lazy_data_loader)
        assert callable(core.db_query_optimizer.batch_insert)
        assert callable(core.db_query_optimizer.get_query_profiler)
        assert callable(core.db_query_optimizer.profiled_query)
        assert callable(core.db_query_optimizer.next_page)
        assert callable(core.db_query_optimizer.prev_page)
        assert callable(core.db_query_optimizer.get_current_cursor)
