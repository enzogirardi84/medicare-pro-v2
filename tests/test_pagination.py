"""Tests para core.pagination."""
from __future__ import annotations

import pytest


class TestPagination:
    """Tests para funciones públicas de core.pagination."""

    def test_pagination_importable(self):
        import core.pagination
        assert core.pagination is not None

    def test_functions_exist(self):
        import core.pagination
        assert callable(core.pagination.render_pagination_controls)
        assert callable(core.pagination.render_lazy_loading_indicator)
        assert callable(core.pagination.calculate_total_pages)
        assert callable(core.pagination.get_cursor_paginator)
        assert callable(core.pagination.get_searchable_paginator)
        assert callable(core.pagination.paginate)
        assert callable(core.pagination.get_page_number)
        assert callable(core.pagination.get_items)
        assert callable(core.pagination.prefetch_background)
        assert callable(core.pagination.search_and_paginate)
