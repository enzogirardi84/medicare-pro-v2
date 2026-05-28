"""Tests para core.config_secure."""
from __future__ import annotations

import pytest


class TestConfigSecure:
    """Tests para funciones públicas de core.config_secure."""

    def test_config_secure_importable(self):
        import core.config_secure
        assert core.config_secure is not None

    def test_functions_exist(self):
        import core.config_secure
        assert callable(core.config_secure.get_settings)
        assert callable(core.config_secure.get_database_url_with_pool)
        assert callable(core.config_secure.validate_environment)
        assert callable(core.config_secure.validate_pool_size)
        assert callable(core.config_secure.validate_supabase_url)
        assert callable(core.config_secure.is_production)
        assert callable(core.config_secure.validate_production_settings)
