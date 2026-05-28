"""Tests para views._recetas_mar."""
from __future__ import annotations

import pytest


class TestRecetasMar:
    """Tests para funciones públicas de views._recetas_mar."""

    def test__recetas_mar_importable(self):
        import views._recetas_mar
        assert views._recetas_mar is not None

    def test_functions_exist(self):
        import views._recetas_mar
        assert callable(views._recetas_mar.registrar_administracion_dosis)
        assert callable(views._recetas_mar.guardar_administracion_medicacion)
        assert callable(views._recetas_mar.construir_matriz_registro_24h)
        assert callable(views._recetas_mar.tabla_guardia_operativa)
        assert callable(views._recetas_mar.tabla_guardia_detallada)
        assert callable(views._recetas_mar.render_marco_clinico_cortina)
        assert callable(views._recetas_mar.render_cortina_mar_hospitalaria)
        assert callable(views._recetas_mar.render_bloque_cortina_medicacion)
        assert callable(views._recetas_mar.render_sabana_compacta)
