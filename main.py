"""Entry point for Streamlit Cloud - Medicare Enterprise PRO.
REDIRIGE al programa principal (main_medicare.py)"""
import sys
from pathlib import Path

# Asegurar que el repo root esté en el path
repo_root = Path(__file__).resolve().parent
root_str = str(repo_root)
if root_str not in sys.path:
    sys.path.insert(0, root_str)

# Importar y ejecutar el programa principal
from main_medicare import *

# Ejecutar la lógica principal
if __name__ == "__main__":
    # Streamlit ejecutará esto automáticamente
    pass