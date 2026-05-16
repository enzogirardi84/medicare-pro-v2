import sys
import time
from pathlib import Path

# Aseguramos que Python encuentre los módulos del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import cargar_datos, supabase
from core.utils import parse_fecha_hora

def migrar_vitales_enfermeria():
    if not supabase:
        print("❌ Error: No hay conexión a Supabase configurada.")
        return

    print("Cargando datos del JSON actual...")
    datos = cargar_datos(force=True, monolito_legacy=True)
    if not datos:
        print("❌ No se encontraron datos locales para migrar.")
        return

    print("Datos JSON cargados. Iniciando migracion a PostgreSQL...\n")
    
    # 1. Obtener mapas de UUIDs existentes (Empresas y Pacientes)
    print("Obteniendo UUIDs de empresas y pacientes...")
    mapa_empresas = {}
    res_emp = supabase.table("empresas").select("id, nombre").execute()
    for emp in res_emp.data:
        mapa_empresas[emp["nombre"]] = emp["id"]
        
    mapa_pacientes = {}
    res_pac = supabase.table("pacientes").select("id, nombre_completo, dni").execute()
    for pac in res_pac.data:
        clave = f"{pac['nombre_completo']} - {pac['dni']}"
        mapa_pacientes[clave] = pac["id"]

    # 2. MIGRAR SIGNOS VITALES
    print("\nMigrando Signos Vitales...")
    vitales_db = datos.get("vitales_db", [])
    count_vitales = 0
    
    for vit in vitales_db:
        if not isinstance(vit, dict): continue
        
        pac_uuid = mapa_pacientes.get(str(vit.get("paciente", "")))
        if not pac_uuid: continue
            
        dt = parse_fecha_hora(str(vit.get("fecha", "")))
        
        # Helper para convertir a numero seguro
        def _to_int(val):
            try: return int(float(str(val).strip()))
            except: return None
            
        def _to_float(val):
            try: return float(str(val).strip())
            except: return None
        
        datos_sql = {
            "paciente_id": pac_uuid,
            "fecha_registro": dt.isoformat() if dt else None,
            "tension_arterial": str(vit.get("TA", ""))[:20],
            "frecuencia_cardiaca": _to_int(vit.get("FC")),
            "frecuencia_respiratoria": _to_int(vit.get("FR")),
            "temperatura": _to_float(vit.get("Temp")),
            "saturacion_oxigeno": _to_int(vit.get("Sat")),
            "glucemia": _to_int(vit.get("HGT")),
            "observaciones": ""
        }
        
        try:
            supabase.table("signos_vitales").insert(datos_sql).execute()
            count_vitales += 1
        except Exception as e:
            print(f"  - Error al migrar signo vital: {e}")
            
    print(f"  - {count_vitales} registros de signos vitales migrados exitosamente.")

    # 3. MIGRAR CUIDADOS DE ENFERMERÍA
    print("\nMigrando Cuidados de Enfermería...")
    cuidados_db = datos.get("cuidados_enfermeria_db", [])
    count_cuidados = 0
    
    for cui in cuidados_db:
        if not isinstance(cui, dict): continue
        
        pac_uuid = mapa_pacientes.get(str(cui.get("paciente", "")))
        if not pac_uuid: continue
            
        dt = parse_fecha_hora(str(cui.get("fecha", "")))
        
        datos_sql = {
            "paciente_id": pac_uuid,
            "fecha_registro": dt.isoformat() if dt else None,
            "tipo_cuidado": str(cui.get("cuidado", ""))[:100],
            "descripcion": str(cui.get("observacion", "")),
            "realizado": str(cui.get("estado", "")).lower() == "realizado"
        }
        
        try:
            supabase.table("cuidados_enfermeria").insert(datos_sql).execute()
            count_cuidados += 1
        except Exception as e:
            print(f"  - Error al migrar cuidado de enfermería: {e}")
            
    print(f"  - {count_cuidados} cuidados de enfermería migrados exitosamente.")

    print("\n!MIGRACION COMPLETADA CON EXITO!")

if __name__ == "__main__":
    migrar_vitales_enfermeria()