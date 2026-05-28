"""Tests para core.ui_optimizer."""
from __future__ import annotations

import pytest


class TestUiOptimizer:
    """Tests para funciones públicas de core.ui_optimizer."""

    def test_ui_optimizer_importable(self):
        import core.ui_optimizer
        assert core.ui_optimizer is not None

    def test_functions_exist(self):
        import core.ui_optimizer
        assert callable(core.ui_optimizer.optimize_dataframe_display)
        assert callable(core.ui_optimizer.paginated_dataframe)
        assert callable(core.ui_optimizer.get_debouncer)
        assert callable(core.ui_optimizer.get_throttler)
        assert callable(core.ui_optimizer.debounced)
        assert callable(core.ui_optimizer.throttled)
        assert callable(core.ui_optimizer.debounce)
        assert callable(core.ui_optimizer.throttle)
        assert callable(core.ui_optimizer.visible_count)
        assert callable(core.ui_optimizer.start_index)
