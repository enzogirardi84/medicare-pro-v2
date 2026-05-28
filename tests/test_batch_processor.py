"""Tests para core.batch_processor."""
from __future__ import annotations

import pytest


class TestBatchProcessor:
    """Tests para funciones públicas de core.batch_processor."""

    def test_batch_processor_importable(self):
        import core.batch_processor
        assert core.batch_processor is not None

    def test_functions_exist(self):
        import core.batch_processor
        assert callable(core.batch_processor.get_batch_processor)
        assert callable(core.batch_processor.create_batch_job)
        assert callable(core.batch_processor.duration_seconds)
        assert callable(core.batch_processor.success_rate)
        assert callable(core.batch_processor.submit_job)
        assert callable(core.batch_processor.run_job)
        assert callable(core.batch_processor.cancel_job)
        assert callable(core.batch_processor.get_job_status)
        assert callable(core.batch_processor.list_active_jobs)
        assert callable(core.batch_processor.record_perf)
