"""Entry point for Streamlit Cloud - Medicare Enterprise PRO"""
import sys
import traceback
from pathlib import Path

# Asegurar path
repo_root = Path(__file__).resolve().parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Barrier: catch ANY import error
try:
    import streamlit as st
    from core.app_bootstrap import insert_repo_root_on_path
    insert_repo_root_on_path()
except Exception as e:
    import subprocess, sys as _sys
    print(f"FATAL BOOT ERROR: {e}")
    _sys.exit(1)

# Ahora import main_medicare con proteccion total
try:
    from core.app_logging import configurar_logging_basico, log_event
    configurar_logging_basico()
except Exception:
    pass

# ============================================================
# MAIN APP - with comprehensive error catching
# ============================================================
try:
    # This does st.set_page_config, render_login, and the full app
    exec(open("main_medicare.py", encoding="utf-8").read())
except Exception as e:
    st.error(f"Error critico en la aplicacion: {type(e).__name__}: {e}")
    st.exception(e)
    st.info("Si ves esto, la app fallo en la carga principal. Revisa los logs de Streamlit Cloud.")
