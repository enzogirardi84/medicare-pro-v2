"""Entry point for Streamlit Cloud - Medicare Enterprise PRO"""
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from core.app_bootstrap import insert_repo_root_on_path
insert_repo_root_on_path()

import main_medicare  # noqa: F401, E402
