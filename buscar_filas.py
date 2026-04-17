import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.database import supabase

def buscar_filas_medicare_db():
    res = supabase.table("medicare_db").select("id, tenant_key").execute()
    print(f"Filas en medicare_db: {res.data}")

if __name__ == "__main__":
    buscar_filas_medicare_db()