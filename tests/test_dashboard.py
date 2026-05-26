"""Tests para views/dashboard.py -- regresiones en módulo principal."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_render_dashboard_importable():
    """Verifica que render_dashboard sea importable sin crashear."""
    from views.dashboard import render_dashboard
    assert callable(render_dashboard)


def test_render_dashboard_acepta_parametros():
    """render_dashboard acepta (mi_empresa, rol) sin crashear al importar."""
    from views.dashboard import render_dashboard
    # Verificar que la función existe y tiene la firma correcta
    import inspect
    sig = inspect.signature(render_dashboard)
    assert "mi_empresa" in sig.parameters
    assert "rol" in sig.parameters


def test_dashboard_utils_importable():
    """Verifica que _dashboard_utils sea importable."""
    from views._dashboard_utils import _sumar_importe, _estado_vital_dash
    assert callable(_sumar_importe)
    assert callable(_estado_vital_dash)


def test_dashboard_bloques_importable():
    """Verifica que _dashboard_bloques sea importable."""
    from views._dashboard_bloques import (
        render_notificaciones_turno,
        render_vitales_alertas,
        render_vista_operativa,
        render_listados_ejecutivos,
    )
    for fn in (render_notificaciones_turno, render_vitales_alertas,
               render_vista_operativa, render_listados_ejecutivos):
        assert callable(fn)
