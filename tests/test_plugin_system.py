"""Tests para core.plugin_system."""
from __future__ import annotations

import pytest


class TestPluginSystem:
    """Tests para funciones públicas de core.plugin_system."""

    def test_plugin_system_importable(self):
        import core.plugin_system
        assert core.plugin_system is not None

    def test_functions_exist(self):
        import core.plugin_system
        assert callable(core.plugin_system.register_hook)
        assert callable(core.plugin_system.get_plugin_manager)
        assert callable(core.plugin_system.trigger_app_hook)
        assert callable(core.plugin_system.get_info)
        assert callable(core.plugin_system.initialize)
        assert callable(core.plugin_system.on_hook)
        assert callable(core.plugin_system.get_config_schema)
        assert callable(core.plugin_system.validate_config)
        assert callable(core.plugin_system.discover_plugins)
        assert callable(core.plugin_system.load_plugin)
