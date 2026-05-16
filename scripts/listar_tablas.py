import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import supabase

def listar_tablas():
    res = supabase.table("medicare_db").select("*").execute()
    print(f"Filas en medicare_db: {len(res.data)}")
    if res.data:
        datos = res.data[0].get("datos", {})
        print(f"Claves en datos: {list(datos.keys())}")
        usuarios = datos.get("usuarios_db", {})
        print(f"Usuarios en datos: {list(usuarios.keys())}")

if __name__ == "__main__":
    listar_tablas()