"""Tests para views.settings.__init__."""
from __future__ import annotations

import pytest


class TestInit:
    """Tests para funciones públicas de views.settings.__init__."""

    def test___init___importable(self):
        import views.settings.__init__
        assert views.settings.__init__ is not None

    def test_functions_exist(self):
        import views.settings.__init__
        assert callable(views.settings.__init__.get_version)
        assert callable(views.settings.__init__.get_environment)
        assert callable(views.settings.__init__.get_python_version)
        assert callable(views.settings.__init__.get_os_info)
        assert callable(views.settings.__init__.render_settings_page)
