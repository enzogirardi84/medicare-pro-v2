"""Bootstrap de rutas y configuración base de MediCare PRO.

Aislado de main.py para que el orquestador solo importe y arranque.
"""

import sys
from pathlib import Path


def insert_repo_root_on_path() -> Path:
    """
    Streamlit Cloud puede ejecutar main.py dentro de una subcarpeta.
    Subimos directorios hasta encontrar core/ y lo agregamos a sys.path.
    """
    here = Path(__file__).resolve().parent.parent
    cur: Path = here
    root = here

    for _ in range(5):
        if (cur / "core").is_dir():
            root = cur
            break
        parent = cur.parent
        if parent == cur:
            break
        cur = parent

    rs = str(root)
    if rs not in sys.path:
        sys.path.insert(0, rs)

    hs = str(here)
    if hs != rs and hs not in sys.path:
        sys.path.insert(0, hs)

    return root


REPO_ROOT = insert_repo_root_on_path()
