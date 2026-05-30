"""Tests para core/perf_metrics.py."""
from __future__ import annotations


def test_record_perf_importable():
    from core.perf_metrics import record_perf
    assert callable(record_perf)


def test_summarize_perf_importable():
    from core.perf_metrics import summarize_perf
    assert callable(summarize_perf)
