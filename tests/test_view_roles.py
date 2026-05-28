"""Tests para core.view_roles."""
from __future__ import annotations

import pytest


class TestViewRoles:
    """Tests para funciones públicas de core.view_roles."""

    def test_view_roles_importable(self):
        import core.view_roles
        assert core.view_roles is not None

    def test_functions_exist(self):
        import core.view_roles
        assert callable(core.view_roles.tiene_acceso_vista)
        assert callable(core.view_roles.modulos_menu_para_rol)
