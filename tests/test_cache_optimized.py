"""Tests para core.cache_optimized."""
from __future__ import annotations

import pytest


class TestCacheOptimized:
    """Tests para funciones públicas de core.cache_optimized."""

    def test_cache_optimized_importable(self):
        import core.cache_optimized
        assert core.cache_optimized is not None

    def test_functions_exist(self):
        import core.cache_optimized
        assert callable(core.cache_optimized.cached_query)
        assert callable(core.cache_optimized.get_obras_sociales)
        assert callable(core.cache_optimized.get_app_config)
        assert callable(core.cache_optimized.init_pagination)
        assert callable(core.cache_optimized.get_obras_sociales_cached)
        assert callable(core.cache_optimized.get_app_config_cached)
        assert callable(core.cache_optimized.get_pdf_templates_cached)
        assert callable(core.cache_optimized.invalidate_cache_key)
        assert callable(core.cache_optimized.safe_set)
        assert callable(core.cache_optimized.get_with_default)
