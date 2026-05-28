"""Tests para views.cierre_diario."""
from __future__ import annotations

import pytest


class TestCierreDiario:
    """Tests para funciones públicas de views.cierre_diario."""

    def test_cierre_diario_importable(self):
        import views.cierre_diario
        assert views.cierre_diario is not None

    def test_functions_exist(self):
        import views.cierre_diario
        assert callable(views.cierre_diario.render_cierre_diario)
        assert callable(views.cierre_diario.generar_pdf_cierre)
