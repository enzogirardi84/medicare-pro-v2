from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_entrypoint_has_no_magic_text_expressions():
    path = ROOT / "streamlit_app.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    loose_strings = [
        node
        for node in tree.body
        if isinstance(node, ast.Expr)
        and isinstance(getattr(node, "value", None), ast.Constant)
        and isinstance(node.value.value, str)
    ]

    assert loose_strings == []


def test_streamlit_entrypoint_executes_main_medicare_each_rerun():
    path = ROOT / "streamlit_app.py"
    source = path.read_text(encoding="utf-8")

    assert "main_medicare.py" in source
    assert "exec(" in source
    assert "import main_medicare" not in source
