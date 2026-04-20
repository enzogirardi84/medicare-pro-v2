import sys
from pathlib import Path

# Aseguramos que Python encuentre los módulos del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.database import cargar_datos, supabase
from core.utils import parse_fecha_hora

def migrar_auditoria():
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

    # 2. MIGRAR AUDITORIA LEGAL
    print("\nMigrando Auditoría Legal...")
    auditoria_db = datos.get("auditoria_legal_db", [])
    count_auditoria = 0
    
    for aud in auditoria_db:
        if not isinstance(aud, dict): continue
        
        emp_uuid = mapa_empresas.get(str(aud.get("empresa", "")))
        if not emp_uuid: continue
            
        pac_uuid = None
        pac_nombre = str(aud.get("paciente", ""))
        if pac_nombre and pac_nombre != "N/A":
            pac_uuid = mapa_pacientes.get(pac_nombre)
            
        dt = parse_fecha_hora(str(aud.get("fecha", "")))
        
        datos_sql = {
            "empresa_id": emp_uuid,
            "paciente_id": pac_uuid,
            "fecha_evento": dt.isoformat() if dt else None,
            "modulo": str(aud.get("modulo", ""))[:50],
            "accion": str(aud.get("accion", ""))[:255],
            "detalle": str(aud.get("detalle", "")),
            "usuario_id": None # No tenemos mapeo directo de usuarios todavia
        }
        
        try:
            supabase.table("auditoria_legal").insert(datos_sql).execute()
            count_auditoria += 1
        except Exception as e:
            print(f"  - Error al migrar log de auditoría: {e}")
            
    print(f"  - {count_auditoria} logs de auditoría migrados exitosamente.")

    print("\n!MIGRACION COMPLETADA CON EXITO!")

if __name__ == "__main__":
    migrar_auditoria()