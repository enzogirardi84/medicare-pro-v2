"""Tests para core.rbac_advanced."""
from __future__ import annotations

import pytest


class TestRbacAdvanced:
    """Tests para funciones públicas de core.rbac_advanced."""

    def test_rbac_advanced_importable(self):
        import core.rbac_advanced
        assert core.rbac_advanced is not None

    def test_functions_exist(self):
        import core.rbac_advanced
        assert callable(core.rbac_advanced.get_rbac_manager)
        assert callable(core.rbac_advanced.require_permission)
        assert callable(core.rbac_advanced.check_user_permission)
        assert callable(core.rbac_advanced.assign_role)
        assert callable(core.rbac_advanced.to_dict)
        assert callable(core.rbac_advanced.assign_role_to_user)
        assert callable(core.rbac_advanced.revoke_role)
        assert callable(core.rbac_advanced.assign_patient_to_user)
        assert callable(core.rbac_advanced.check_permission)
        assert callable(core.rbac_advanced.get_user_permissions)
