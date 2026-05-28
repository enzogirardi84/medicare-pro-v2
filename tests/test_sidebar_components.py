"""Tests para core.sidebar_components."""
from __future__ import annotations

import pytest


class TestSidebarComponents:
    """Tests para funciones públicas de core.sidebar_components."""

    def test_sidebar_components_importable(self):
        import core.sidebar_components
        assert core.sidebar_components is not None

    def test_functions_exist(self):
        import core.sidebar_components
        assert callable(core.sidebar_components.sidebar_patient_card)
        assert callable(core.sidebar_components.sidebar_brand_card)
        assert callable(core.sidebar_components.semaforo_vital_sidebar)
        assert callable(core.sidebar_components.render_sidebar_contexto_clinico)
        assert callable(core.sidebar_components.render_mobile_contexto_clinico)
        assert callable(core.sidebar_components.render_sidebar_pacientes_y_alertas)
