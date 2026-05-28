"""Tests para core.search_engine."""
from __future__ import annotations

import pytest


class TestSearchEngine:
    """Tests para funciones públicas de core.search_engine."""

    def test_search_engine_importable(self):
        import core.search_engine
        assert core.search_engine is not None

    def test_functions_exist(self):
        import core.search_engine
        assert callable(core.search_engine.get_search_manager)
        assert callable(core.search_engine.quick_search)
        assert callable(core.search_engine.add_document)
        assert callable(core.search_engine.remove_document)
        assert callable(core.search_engine.search)
        assert callable(core.search_engine.get_suggestions)
        assert callable(core.search_engine.get_stats)
        assert callable(core.search_engine.index_all_data)
        assert callable(core.search_engine.search_patients)
        assert callable(core.search_engine.search_medical_records)
