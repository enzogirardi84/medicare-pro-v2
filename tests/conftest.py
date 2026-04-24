import sys
from pathlib import Path

# Agregar el directorio raiz del repositorio a sys.path para que los tests
# puedan importar core, features, views, services, etc. sin depender de
# PYTHONPATH ni de la forma en que pytest lee pyproject.toml.
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))
