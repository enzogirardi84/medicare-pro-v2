from __future__ import annotations

_STREAMLIT_ENTRYPOINT_NOTE = """


Entry point canónico para Streamlit Cloud — MediCare Enterprise PRO.

Autodetected by Streamlit Cloud (convention over configuration).
All Streamlit logic lives in main_medicare.py — do not modify this file.
"""
from pathlib import Path
import sys

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    exec(
        compile(
            (_REPO_ROOT / "main_medicare.py").read_text(encoding="utf-8"),
            "main_medicare.py",
            "exec",
        )
    )
except (SyntaxError, IndentationError) as compile_err:
    st.error("Error de compilacion. Recargue la pagina o contacte a soporte.")
    st.caption(f"Detalle: {compile_err}")
    st.stop()
except KeyError as missing_module:
    st.error("Error interno. Recargue la pagina.")
    st.caption(f"Detalle: modulo no encontrado: {missing_module}")
    st.stop()
except Exception as run_err:
    st.error("Error al iniciar la aplicacion. Recargue la pagina.")
    st.caption(f"Detalle: {run_err}")
    st.stop()
