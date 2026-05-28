"""Tests para core.permissions."""
from __future__ import annotations

import pytest


class TestPermissions:
    """Tests para funciones públicas de core.permissions."""

    def test_permissions_importable(self):
        import core.permissions
        assert core.permissions is not None

    def test_functions_exist(self):
        import core.permissions
        assert callable(core.permissions.normalizar_rol)
        assert callable(core.permissions.rol_usuario)
        assert callable(core.permissions.es_admin)
        assert callable(core.permissions.es_superadmin)
        assert callable(core.permissions.puede)
        assert callable(core.permissions.requiere_permiso)
        assert callable(core.permissions.filtrar_acciones_permitidas)
