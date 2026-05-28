"""Tests para core.utils_ui."""
from __future__ import annotations

import pytest


class TestUtilsUi:
    """Tests para funciones públicas de core.utils_ui."""

    def test_utils_ui_importable(self):
        import core.utils_ui
        assert core.utils_ui is not None

    def test_functions_exist(self):
        import core.utils_ui
        assert callable(core.utils_ui.modo_celular_viejo_activo)
        assert callable(core.utils_ui.valor_por_modo_liviano)
        assert callable(core.utils_ui.cargar_texto_asset)
        assert callable(core.utils_ui.cargar_json_asset)
        assert callable(core.utils_ui.optimizar_imagen_bytes)
        assert callable(core.utils_ui.limite_archivo_mb)
        assert callable(core.utils_ui.validar_archivo_bytes)
        assert callable(core.utils_ui.preparar_imagen_clinica_bytes)
        assert callable(core.utils_ui.obtener_config_firma)
        assert callable(core.utils_ui.firma_a_base64)
