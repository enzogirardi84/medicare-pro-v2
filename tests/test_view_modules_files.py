"""Comprueba que cada entrada de VIEW_CONFIG apunta a un archivo views/*.py existente."""

import ast
import importlib.util
from pathlib import Path

from core.view_registry import VIEW_CONFIG_BASE


def test_cada_modulo_registrado_tiene_archivo_en_views():
    root = Path(__file__).resolve().parents[1]
    for titulo, (package, fn) in VIEW_CONFIG_BASE.items():
        assert package.startswith("views."), titulo
        rest = package.split(".", 1)[1]
        path = root / "views" / f"{rest}.py"
        assert path.is_file(), f"Esperado {path} para «{titulo}» ({package}.{fn})"


def test_cada_vista_declara_funcion_render_en_modulo():
    """
    Verificación estática (AST): evita importar views/ (deps pesadas) y detecta
    typos entre view_registry y el nombre real de la función.
    """

    root = Path(__file__).resolve().parents[1]
    for titulo, (package, fn) in VIEW_CONFIG_BASE.items():
        rest = package.split(".", 1)[1]
        path = root / "views" / f"{rest}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        toplevel = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert fn in toplevel, f"{path}: falta «def {fn}» registrado para «{titulo}»"


def test_cada_paquete_views_resoluble_sin_ejecutar_modulo():
    """importlib encuentra el spec del submodulo (no importa el .py completo)."""
    for titulo, (package, _fn) in VIEW_CONFIG_BASE.items():
        spec = importlib.util.find_spec(package)
        assert spec is not None, f"«{titulo}»: find_spec({package!r})"
        assert spec.origin and spec.origin.endswith(".py"), titulo
