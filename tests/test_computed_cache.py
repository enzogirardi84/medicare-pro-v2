"""Tests para core.computed_cache."""
from __future__ import annotations

import pytest


class TestComputedCache:
    """Tests para funciones públicas de core.computed_cache."""

    def test_computed_cache_importable(self):
        import core.computed_cache
        assert core.computed_cache is not None

    def test_functions_exist(self):
        import core.computed_cache
        assert callable(core.computed_cache.cached_computed)
        assert callable(core.computed_cache.invalidate_computed)
        assert callable(core.computed_cache.invalidate_all_computed)
