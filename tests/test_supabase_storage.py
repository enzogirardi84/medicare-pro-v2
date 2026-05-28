"""Tests para core.supabase_storage."""
from __future__ import annotations

import pytest


class TestSupabaseStorage:
    """Tests para funciones públicas de core.supabase_storage."""

    def test_supabase_storage_importable(self):
        import core.supabase_storage
        assert core.supabase_storage is not None

    def test_functions_exist(self):
        import core.supabase_storage
        assert callable(core.supabase_storage.get_supabase_storage)
        assert callable(core.supabase_storage.guardar_signos_vitales_seguro)
        assert callable(core.supabase_storage.obtener_signos_vitales_paciente)
        assert callable(core.supabase_storage.guardar_signos_vitales)
        assert callable(core.supabase_storage.obtener_signos_vitales)
        assert callable(core.supabase_storage.contar_signos_vitales)
