"""Tests para core.alertas_medicacion."""
from __future__ import annotations

import pytest


class TestAlertasMedicacion:
    """Tests para funciones públicas de core.alertas_medicacion."""

    def test_alertas_medicacion_importable(self):
        import core.alertas_medicacion
        assert core.alertas_medicacion is not None

    def test_functions_exist(self):
        import core.alertas_medicacion
        assert callable(core.alertas_medicacion.verificar_alergias_medicacion)
        assert callable(core.alertas_medicacion.render_alertas_medicacion)
