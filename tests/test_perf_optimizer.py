"""Tests para core.perf_optimizer."""
from __future__ import annotations

import pytest


class TestPerfOptimizer:
    """Tests para funciones públicas de core.perf_optimizer."""

    def test_perf_optimizer_importable(self):
        import core.perf_optimizer
        assert core.perf_optimizer is not None

    def test_functions_exist(self):
        import core.perf_optimizer
        assert callable(core.perf_optimizer.track_render_time)
        assert callable(core.perf_optimizer.get_render_stats)
        assert callable(core.perf_optimizer.clear_module_state)
        assert callable(core.perf_optimizer.cleanup_orphan_session_vars)
        assert callable(core.perf_optimizer.get_cached_catalogos)
        assert callable(core.perf_optimizer.get_cached_pacientes_resumen)
        assert callable(core.perf_optimizer.get_db_connection_pool)
        assert callable(core.perf_optimizer.should_rerender)
        assert callable(core.perf_optimizer.memoize_component)
        assert callable(core.perf_optimizer.lazy_load_large_dataset)
