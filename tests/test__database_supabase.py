"""Tests para core._database_supabase."""
from __future__ import annotations

import pytest


class TestDatabaseSupabase:
    """Tests para funciones públicas de core._database_supabase."""

    def test__database_supabase_importable(self):
        import core._database_supabase
        assert core._database_supabase is not None

    def test_functions_exist(self):
        import core._database_supabase
        assert callable(core._database_supabase.init_supabase)
