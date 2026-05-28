"""Tests para core.clinicas_control."""
from __future__ import annotations

import pytest


class TestClinicasControl:
    """Tests para funciones públicas de core.clinicas_control."""

    def test_clinicas_control_importable(self):
        import core.clinicas_control
        assert core.clinicas_control is not None

    def test_functions_exist(self):
        import core.clinicas_control
        assert callable(core.clinicas_control.obtener_registro_clinica)
        assert callable(core.clinicas_control.clinica_suspendida)
        assert callable(core.clinicas_control.rol_bypass_suspend_clinica)
        assert callable(core.clinicas_control.login_bloqueado_por_clinica)
        assert callable(core.clinicas_control.sincronizar_clinicas_desde_datos)
        assert callable(core.clinicas_control.suspender_clinica)
        assert callable(core.clinicas_control.reactivar_clinica)
        assert callable(core.clinicas_control.contar_usuarios_por_clinica)
