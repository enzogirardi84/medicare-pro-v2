import sys
import time
from pathlib import Path

# Aseguramos que Python encuentre los módulos del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import supabase
import json

def recuperar_usuarios():
    if not supabase:
        print("❌ Error: No hay conexión a Supabase configurada.")
        return

    print("Buscando backup del monolito en Supabase...")
    res = supabase.table("medicare_db").select("datos").eq("id", 1).execute()
    
    if not res.data:
        print("❌ No se encontró el monolito en Supabase.")
        return
        
    datos = res.data[0]["datos"]
    usuarios = datos.get("usuarios_db", {})
    
    print(f"Se encontraron {len(usuarios)} usuarios en el backup de Supabase.")
    
    # Escribir a un archivo para verlos
    with open("usuarios_backup.json", "w", encoding="utf-8") as f:
        json.dump(usuarios, f, indent=2, ensure_ascii=False)
        
    print("Usuarios guardados en usuarios_backup.json")

if __name__ == "__main__":
    recuperar_usuarios()