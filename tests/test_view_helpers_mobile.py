from __future__ import annotations

import inspect

from core import view_helpers


def test_compactacion_movil_considera_viewport_cliente():
    src = inspect.getsource(view_helpers.aplicar_compactacion_movil_por_vista)

    assert "matchMedia" in src
    assert "(max-width: 767px)" in src
    assert "viewportWantsCompact" in src
    assert "serverWantsCompact" in src
