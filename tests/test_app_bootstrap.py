"""Tests para core.app_bootstrap."""
from __future__ import annotations

import pytest


class TestAppBootstrap:
    """Tests para funciones públicas de core.app_bootstrap."""

    def test_app_bootstrap_importable(self):
        import core.app_bootstrap
        assert core.app_bootstrap is not None

    def test_functions_exist(self):
        import core.app_bootstrap
        assert callable(core.app_bootstrap.insert_repo_root_on_path)
