"""Tests para core.pacientes."""
from __future__ import annotations

import pytest


class TestPacientes:
    """Tests para funciones públicas de core.pacientes."""

    def test_pacientes_importable(self):
        import core.pacientes
        assert core.pacientes is not None

    def test_functions_exist(self):
        import core.pacientes
        assert callable(core.pacientes.registrar_auditoria)
        assert callable(core.pacientes.alta_paciente)
        assert callable(core.pacientes.buscar_paciente)
        assert callable(core.pacientes.actualizar_paciente)
        assert callable(core.pacientes.obtener_historial)
