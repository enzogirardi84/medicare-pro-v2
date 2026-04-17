import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.database import supabase

def buscar_usuarios_sql():
    res = supabase.table("usuarios").select("*").execute()
    print(f"Usuarios en SQL: {len(res.data)}")
    for u in res.data:
        print(f" - {u['nombre']} ({u['rol']})")

if __name__ == "__main__":
    buscar_usuarios_sql()