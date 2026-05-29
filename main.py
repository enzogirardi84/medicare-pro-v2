"""Entry point for Streamlit Cloud - Medicare Enterprise PRO"""

from __future__ import annotations

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from core.app_bootstrap import insert_repo_root_on_path
insert_repo_root_on_path()

import streamlit as st

# Ejecutar main_medicare.py fresco en cada rerun (necesario para Streamlit)
try:
    exec(compile(open("main_medicare.py", encoding="utf-8").read(), "main_medicare.py", "exec"))
except (SyntaxError, IndentationError) as _compile_err:
    st.error(f"Error de compilacion. Recargue la pagina o contacte a soporte.")
    st.caption(f"Detalle: {_compile_err}")
except Exception as _run_err:
    st.error(f"Error al iniciar la aplicacion. Recargue la pagina.")
    st.caption(f"Detalle: {_run_err}")
