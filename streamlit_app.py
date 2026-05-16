"""
Entry point canónico para Streamlit Cloud — MediCare Enterprise PRO.

Autodetected by Streamlit Cloud (convention over configuration).
All Streamlit logic lives in main_medicare.py — do not modify this file.
"""
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import main_medicare  # noqa: F401, E402
