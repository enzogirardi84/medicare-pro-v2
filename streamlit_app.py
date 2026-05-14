"""
Entry point canónico para Streamlit Cloud — MediCare Enterprise PRO.

Streamlit Cloud autodetecta este archivo por convención (streamlit_app.py)
y lo prioriza sobre cualquier otro main.py.

NO modificar este archivo. Si necesitás cambiar el comportamiento del boot,
hacelo en main_medicare.py.

Fix 2026-05-14: Resuelve la ambigüedad entre main.py (que carga billing)
y main_medicare.py (que carga el programa principal).
"""
from pathlib import Path
import sys

# Garantizar que el repo raíz esté en sys.path antes que cualquier import del programa
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Cargar el programa principal de MediCare (NO el billing)
# Toda la lógica de Streamlit vive en main_medicare.py
import main_medicare  # noqa: F401, E402  pylint: disable=unused-import
