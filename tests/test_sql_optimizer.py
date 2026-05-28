"""Tests para core.sql_optimizer."""
from __future__ import annotations

import pytest


class TestSqlOptimizer:
    """Tests para funciones públicas de core.sql_optimizer."""

    def test_sql_optimizer_importable(self):
        import core.sql_optimizer
        assert core.sql_optimizer is not None

    def test_functions_exist(self):
        import core.sql_optimizer
        assert callable(core.sql_optimizer.get_sql_optimizer)
        assert callable(core.sql_optimizer.get_query_profiler)
        assert callable(core.sql_optimizer.get_index_recommendations)
        assert callable(core.sql_optimizer.analyze_query)
        assert callable(core.sql_optimizer.get_index_recommendations)
        assert callable(core.sql_optimizer.generate_create_index_sql)
        assert callable(core.sql_optimizer.get_missing_indexes_report)
        assert callable(core.sql_optimizer.analyze_query)
        assert callable(core.sql_optimizer.build_optimized_select)
        assert callable(core.sql_optimizer.build_batch_insert)
