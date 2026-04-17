import sys
import time
from pathlib import Path

# Aseguramos que Python encuentre los módulos del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.database import cargar_datos, supabase
from core.utils import parse_fecha_hora

def migrar_clinicas_restantes():
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

    # Helpers
    def _to_float(val):
        try: return float(str(val).strip())
        except: return None
        
    def _to_int(val):
        try: return int(float(str(val).strip()))
        except: return None

    # 2. MIGRAR CONSENTIMIENTOS
    print("\nMigrando Consentimientos...")
    consentimientos_db = datos.get("consentimientos_db", [])
    count_cons = 0
    
    for cons in consentimientos_db:
        if not isinstance(cons, dict): continue
        
        pac_uuid = mapa_pacientes.get(str(cons.get("paciente", "")))
        if not pac_uuid: continue
            
        dt = parse_fecha_hora(str(cons.get("fecha", "")))
        
        datos_sql = {
            "paciente_id": pac_uuid,
            "fecha_firma": dt.isoformat() if dt else None,
            "tipo_documento": str(cons.get("tipo", "Consentimiento General"))[:100],
            "archivo_url": None, # Las firmas en base64 se migrarán a Storage si es necesario, por ahora nulo
            "observaciones": str(cons.get("observaciones", ""))
        }
        
        try:
            supabase.table("consentimientos").insert(datos_sql).execute()
            count_cons += 1
        except Exception as e:
            print(f"  - Error al migrar consentimiento: {e}")
            
    print(f"  - {count_cons} consentimientos migrados exitosamente.")

    # 3. MIGRAR PEDIATRÍA
    print("\nMigrando Pediatría...")
    pediatria_db = datos.get("pediatria_db", [])
    count_ped = 0
    
    for ped in pediatria_db:
        if not isinstance(ped, dict): continue
        
        pac_uuid = mapa_pacientes.get(str(ped.get("paciente", "")))
        if not pac_uuid: continue
            
        dt = parse_fecha_hora(str(ped.get("fecha", "")))
        
        datos_sql = {
            "paciente_id": pac_uuid,
            "fecha_registro": dt.isoformat() if dt else None,
            "peso_kg": _to_float(ped.get("peso")),
            "talla_cm": _to_float(ped.get("talla")),
            "perimetro_cefalico_cm": _to_float(ped.get("perimetro_cefalico")),
            "percentilo_peso": str(ped.get("percentilo_peso", ""))[:20],
            "percentilo_talla": str(ped.get("percentilo_talla", ""))[:20],
            "observaciones": str(ped.get("observaciones", ""))
        }
        
        try:
            supabase.table("pediatria").insert(datos_sql).execute()
            count_ped += 1
        except Exception as e:
            print(f"  - Error al migrar pediatría: {e}")
            
    print(f"  - {count_ped} registros de pediatría migrados exitosamente.")

    # 4. MIGRAR ESCALAS CLÍNICAS
    print("\nMigrando Escalas Clínicas...")
    escalas_db = datos.get("escalas_clinicas_db", [])
    count_esc = 0
    
    for esc in escalas_db:
        if not isinstance(esc, dict): continue
        
        pac_uuid = mapa_pacientes.get(str(esc.get("paciente", "")))
        if not pac_uuid: continue
            
        dt = parse_fecha_hora(str(esc.get("fecha", "")))
        
        datos_sql = {
            "paciente_id": pac_uuid,
            "fecha_registro": dt.isoformat() if dt else None,
            "tipo_escala": str(esc.get("escala", "Escala General"))[:100],
            "puntaje_total": _to_int(esc.get("puntaje_total") or esc.get("puntaje")),
            "interpretacion": str(esc.get("interpretacion", ""))[:255],
            "observaciones": str(esc.get("observaciones", ""))
        }
        
        try:
            supabase.table("escalas_clinicas").insert(datos_sql).execute()
            count_esc += 1
        except Exception as e:
            print(f"  - Error al migrar escala: {e}")
            
    print(f"  - {count_esc} registros de escalas migrados exitosamente.")

    # 5. MIGRAR EMERGENCIAS
    print("\nMigrando Emergencias...")
    emergencias_db = datos.get("emergencias_db", [])
    count_emg = 0
    
    for emg in emergencias_db:
        if not isinstance(emg, dict): continue
        
        emp_uuid = mapa_empresas.get(str(emg.get("empresa", "")))
        if not emp_uuid: continue
            
        pac_uuid = None
        pac_nombre = str(emg.get("paciente", ""))
        if pac_nombre and pac_nombre != "N/A":
            pac_uuid = mapa_pacientes.get(pac_nombre)
            
        dt = parse_fecha_hora(str(emg.get("fecha", "")))
        
        datos_sql = {
            "empresa_id": emp_uuid,
            "paciente_id": pac_uuid,
            "fecha_llamado": dt.isoformat() if dt else None,
            "motivo": str(emg.get("motivo", "Sin motivo especificado")),
            "prioridad": str(emg.get("prioridad", "Verde"))[:50],
            "estado": str(emg.get("estado", "Pendiente"))[:50],
            "resolucion": str(emg.get("resolucion", "")),
            "recursos_asignados": str(emg.get("recursos", ""))
        }
        
        try:
            supabase.table("emergencias").insert(datos_sql).execute()
            count_emg += 1
        except Exception as e:
            print(f"  - Error al migrar emergencia: {e}")
            
    print(f"  - {count_emg} registros de emergencias migrados exitosamente.")

    print("\n!MIGRACION COMPLETADA CON EXITO!")

if __name__ == "__main__":
    migrar_clinicas_restantes()