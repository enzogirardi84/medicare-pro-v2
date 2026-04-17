import sys
import time
from pathlib import Path

# Aseguramos que Python encuentre los módulos del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.database import cargar_datos, supabase

def migrar_usuarios():
    if not supabase:
        print("❌ Error: No hay conexión a Supabase configurada.")
        return

    print("Cargando datos del JSON actual...")
    # Leer el JSON directamente del disco para evitar el bypass de cargar_datos
    import json
    from core.database import LOCAL_DB_PATH
    
    try:
        if LOCAL_DB_PATH.exists():
            datos = json.loads(LOCAL_DB_PATH.read_bytes())
        else:
            print("❌ No se encontró el archivo local_data.json")
            return
    except Exception as e:
        print(f"❌ Error leyendo JSON: {e}")
        return

    print("Datos JSON cargados. Iniciando migracion de usuarios a PostgreSQL...\n")
    
    # 1. Obtener mapas de UUIDs de empresas
    print("Obteniendo UUIDs de empresas...")
    mapa_empresas = {}
    res_emp = supabase.table("empresas").select("id, nombre").execute()
    for emp in res_emp.data:
        mapa_empresas[emp["nombre"]] = emp["id"]

    # 2. MIGRAR USUARIOS
    print("\nMigrando Usuarios...")
    usuarios_db = datos.get("usuarios_db", {})
    count_usr = 0
    
    for login, usr in usuarios_db.items():
        if not isinstance(usr, dict): continue
        if login == "admin": continue # El admin de emergencia no se migra
        
        emp_nombre = str(usr.get("empresa", "Clinica General")).strip()
        emp_uuid = mapa_empresas.get(emp_nombre)
        
        # Si la empresa no existe en SQL, la creamos al vuelo
        if not emp_uuid and emp_nombre:
            try:
                res = supabase.table("empresas").upsert({"nombre": emp_nombre}, on_conflict="nombre").execute()
                if res.data:
                    emp_uuid = res.data[0]["id"]
                    mapa_empresas[emp_nombre] = emp_uuid
                    print(f"  - Empresa creada al vuelo: {emp_nombre}")
            except Exception as e:
                print(f"  - Error creando empresa {emp_nombre}: {e}")
                continue
                
        datos_sql = {
            "empresa_id": emp_uuid,
            "nombre": str(usr.get("nombre", login))[:255],
            "password_hash": str(usr.get("pass", ""))[:255],
            "rol": str(usr.get("rol", "Operativo"))[:50],
            "matricula": str(usr.get("matricula", ""))[:50],
            "dni": str(usr.get("dni", ""))[:50],
            "titulo": str(usr.get("titulo", ""))[:100],
            "estado": str(usr.get("estado", "Activo"))[:50],
            "email": str(usr.get("email", ""))[:255]
        }
        
        try:
            # Buscamos si ya existe por nombre y empresa
            res_exist = supabase.table("usuarios").select("id").eq("nombre", datos_sql["nombre"]).eq("empresa_id", emp_uuid).execute()
            if not res_exist.data:
                supabase.table("usuarios").insert(datos_sql).execute()
                count_usr += 1
            else:
                print(f"  - Usuario ya existe: {datos_sql['nombre']}")
        except Exception as e:
            print(f"  - Error al migrar usuario {login}: {e}")
            
    print(f"  - {count_usr} usuarios migrados exitosamente.")
    print("\n!MIGRACION COMPLETADA CON EXITO!")

if __name__ == "__main__":
    migrar_usuarios()