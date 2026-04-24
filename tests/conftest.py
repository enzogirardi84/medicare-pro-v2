import sys
from pathlib import Path
from unittest.mock import MagicMock

# Mockear streamlit ANTES de que cualquier test importe modulos que lo usan
# (evita ImportError en CI donde Streamlit no puede inicializarse)
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit_drawable_canvas"] = MagicMock()

# Agregar el directorio raiz del repositorio a sys.path para que los tests
# puedan importar core, features, views, services, etc. sin depender de
# PYTHONPATH ni de la forma en que pytest lee pyproject.toml.
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))
