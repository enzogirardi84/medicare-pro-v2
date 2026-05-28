"""Tests para core.seguridad_operaciones."""
from __future__ import annotations

import pytest


class TestSeguridadOperaciones:
    """Tests para funciones públicas de core.seguridad_operaciones."""

    def test_seguridad_operaciones_importable(self):
        import core.seguridad_operaciones
        assert core.seguridad_operaciones is not None

    def test_functions_exist(self):
        import core.seguridad_operaciones
        assert callable(core.seguridad_operaciones.auto_backup_antes_de_eliminar)
        assert callable(core.seguridad_operaciones.confirmar_antes_de_eliminar)
        assert callable(core.seguridad_operaciones.boton_eliminar_seguro)
        assert callable(core.seguridad_operaciones.deshacer_ultima_operacion)
        assert callable(core.seguridad_operaciones.render_panel_seguridad)
