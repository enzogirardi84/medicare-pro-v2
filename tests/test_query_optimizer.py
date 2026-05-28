"""Tests para core.query_optimizer."""
from __future__ import annotations

import pytest


class TestQueryOptimizer:
    """Tests para funciones públicas de core.query_optimizer."""

    def test_query_optimizer_importable(self):
        import core.query_optimizer
        assert core.query_optimizer is not None

    def test_functions_exist(self):
        import core.query_optimizer
        assert callable(core.query_optimizer.get_query_optimizer)
        assert callable(core.query_optimizer.create_bloom_filter)
        assert callable(core.query_optimizer.compress_large_data)
        assert callable(core.query_optimizer.decompress_if_needed)
        assert callable(core.query_optimizer.add)
        assert callable(core.query_optimizer.build)
        assert callable(core.query_optimizer.lookup)
        assert callable(core.query_optimizer.exists)
        assert callable(core.query_optimizer.get_stats)
        assert callable(core.query_optimizer.find_insertion_point)
