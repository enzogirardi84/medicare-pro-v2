"""Tests para views.ai_features_panel."""
from __future__ import annotations

import pytest


class TestAiFeaturesPanel:
    """Tests para funciones públicas de views.ai_features_panel."""

    def test_ai_features_panel_importable(self):
        import views.ai_features_panel
        assert views.ai_features_panel is not None

    def test_functions_exist(self):
        import views.ai_features_panel
        assert callable(views.ai_features_panel.render_ai_features_panel)
        assert callable(views.ai_features_panel.render_resumen)
        assert callable(views.ai_features_panel.render_codificacion)
        assert callable(views.ai_features_panel.render_busqueda)
        assert callable(views.ai_features_panel.render_poblacion)
        assert callable(views.ai_features_panel.render_clinico)
