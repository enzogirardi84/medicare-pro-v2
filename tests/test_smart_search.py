"""Tests para core.smart_search."""
from __future__ import annotations

import pytest


class TestSmartSearch:
    """Tests para funciones públicas de core.smart_search."""

    def test_smart_search_importable(self):
        import core.smart_search
        assert core.smart_search is not None

    def test_functions_exist(self):
        import core.smart_search
        assert callable(core.smart_search.render_smart_search_bar)
        assert callable(core.smart_search.render_search_filters)
        assert callable(core.smart_search.render_search_result_card)
        assert callable(core.smart_search.render_search_results)
        assert callable(core.smart_search.smart_search_pacientes)
        assert callable(core.smart_search.render_sidebar_smart_search)
        assert callable(core.smart_search.search)
        assert callable(core.smart_search.get_suggestions)
