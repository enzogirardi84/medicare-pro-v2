"""Tests para core.utils_roles."""
from __future__ import annotations

import pytest


class TestUtilsRoles:
    """Tests para funciones públicas de core.utils_roles."""

    def test_utils_roles_importable(self):
        import core.utils_roles
        assert core.utils_roles is not None

    def test_functions_exist(self):
        import core.utils_roles
        assert callable(core.utils_roles.empresas_clinica_coinciden)
        assert callable(core.utils_roles.inferir_perfil_profesional)
        assert callable(core.utils_roles.clave_menu_usuario)
        assert callable(core.utils_roles.tiene_permiso)
        assert callable(core.utils_roles.puede_eliminar_cuenta_equipo)
        assert callable(core.utils_roles.puede_suspender_reactivar_usuario_mi_equipo)
        assert callable(core.utils_roles.mi_equipo_actor_es_superadmin)
        assert callable(core.utils_roles.mi_equipo_coordinador_puede_eliminar_objetivo)
        assert callable(core.utils_roles.mi_equipo_mostrar_ui_suspender)
        assert callable(core.utils_roles.mi_equipo_mostrar_ui_eliminar)
