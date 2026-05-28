"""Tests para views.project_management."""
from __future__ import annotations

import pytest


class TestProjectManagement:
    """Tests para funciones públicas de views.project_management."""

    def test_project_management_importable(self):
        import views.project_management
        assert views.project_management is not None

    def test_functions_exist(self):
        import views.project_management
        assert callable(views.project_management.render_project_management)
