"""Tests para core.keyboard_shortcuts."""
from __future__ import annotations

import pytest


class TestKeyboardShortcuts:
    """Tests para funciones públicas de core.keyboard_shortcuts."""

    def test_keyboard_shortcuts_importable(self):
        import core.keyboard_shortcuts
        assert core.keyboard_shortcuts is not None

    def test_functions_exist(self):
        import core.keyboard_shortcuts
        assert callable(core.keyboard_shortcuts.get_shortcut_manager)
        assert callable(core.keyboard_shortcuts.register_default_shortcuts)
        assert callable(core.keyboard_shortcuts.render_shortcuts_help)
        assert callable(core.keyboard_shortcuts.render_keyboard_hint)
        assert callable(core.keyboard_shortcuts.render_command_palette)
        assert callable(core.keyboard_shortcuts.inject_shortcuts_js)
        assert callable(core.keyboard_shortcuts.init_keyboard_shortcuts)
        assert callable(core.keyboard_shortcuts.check_shortcut_triggered)
        assert callable(core.keyboard_shortcuts.demo_keyboard_shortcuts)
        assert callable(core.keyboard_shortcuts.register)
