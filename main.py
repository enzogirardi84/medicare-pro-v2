"""Entry point for Streamlit Cloud - Medicare Enterprise PRO.
REDIRIGE al programa principal (main_medicare.py)"""
import sys
from pathlib import Path

# Asegurar que el repo root esté en el path
repo_root = Path(__file__).resolve().parent
root_str = str(repo_root)
if root_str not in sys.path:
    sys.path.insert(0, root_str)

# Importar el programa principal (ejecuta st.set_page_config y render)
import main_medicare  # noqa: F401