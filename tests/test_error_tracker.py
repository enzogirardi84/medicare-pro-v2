"""Tests para core.error_tracker."""
from __future__ import annotations

import pytest


class TestErrorTracker:
    """Tests para funciones públicas de core.error_tracker."""

    def test_error_tracker_importable(self):
        import core.error_tracker
        assert core.error_tracker is not None

    def test_functions_exist(self):
        import core.error_tracker
        assert callable(core.error_tracker.report_exception)
        assert callable(core.error_tracker.get_recent_errors)
        assert callable(core.error_tracker.get_summary_stats)
        assert callable(core.error_tracker.mark_resolved)
        assert callable(core.error_tracker.clear_all)
        assert callable(core.error_tracker.export_json)
        assert callable(core.error_tracker.setup_global_hooks)
        assert callable(core.error_tracker.resilient)
        assert callable(core.error_tracker.decorator)
        assert callable(core.error_tracker.wrapper)
