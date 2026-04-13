"""Comprueba que cada entrada de VIEW_CONFIG apunta a un archivo views/*.py existente."""

from pathlib import Path

from core.view_registry import VIEW_CONFIG_BASE


def test_cada_modulo_registrado_tiene_archivo_en_views():
    root = Path(__file__).resolve().parents[1]
    for titulo, (package, fn) in VIEW_CONFIG_BASE.items():
        assert package.startswith("views."), titulo
        rest = package.split(".", 1)[1]
        path = root / "views" / f"{rest}.py"
        assert path.is_file(), f"Esperado {path} para «{titulo}» ({package}.{fn})"
