"""Tests para views.factura_electronica."""
from __future__ import annotations

import pytest


class TestFacturaElectronica:
    """Tests para funciones públicas de views.factura_electronica."""

    def test_factura_electronica_importable(self):
        import views.factura_electronica
        assert views.factura_electronica is not None

    def test_functions_exist(self):
        import views.factura_electronica
        assert callable(views.factura_electronica.render_factura_electronica)
