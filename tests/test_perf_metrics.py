"""Tests para core.perf_metrics."""
from __future__ import annotations

import pytest


class TestPerfMetrics:
    """Tests para funciones públicas de core.perf_metrics."""

    def test_perf_metrics_importable(self):
        import core.perf_metrics
        assert core.perf_metrics is not None

    def test_functions_exist(self):
        import core.perf_metrics
        assert callable(core.perf_metrics.record_perf)
        assert callable(core.perf_metrics.summarize_perf)
