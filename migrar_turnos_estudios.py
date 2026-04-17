import sys
import time
from pathlib import Path

# Aseguramos que Python encuentre los módulos del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.database import cargar_datos, supabase
from core.utils import parse_fecha_hora

def migrar_turnos_estudios():
    if not supabase:
        print("❌ Error: No hay conexión a Supabase configurada en .streamlit/secrets.toml")
        return

    print("Cargando datos del JSON actual...")
    # Cargamos la base de datos JSON completa
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
        # Reconstruimos la clave visual "Nombre - DNI"
        clave = f"{pac['nombre_completo']} - {pac['dni']}"
        mapa_pacientes[clave] = pac["id"]

    # 2. MIGRAR TURNOS (AGENDA)
    print("\nMigrando Turnos de la Agenda...")
    turnos_db = datos.get("agenda_db", [])
    count_turnos = 0
    
    for turno in turnos_db:
        if not isinstance(turno, dict): continue
        
        pac_id_viejo = str(turno.get("paciente", ""))
        pac_uuid = mapa_pacientes.get(pac_id_viejo)
        
        empresa_nombre = str(turno.get("empresa", "Clinica General"))
        empresa_uuid = mapa_empresas.get(empresa_nombre)
        
        if not pac_uuid or not empresa_uuid:
            print(f"  - Saltando turno de {pac_id_viejo} (Paciente o Empresa no encontrados en SQL)")
            continue
            
        # Parsear fecha y hora
        fecha_str = str(turno.get("fecha_hora_programada", ""))
        if not fecha_str:
            fecha = str(turno.get("fecha_programada", "") or turno.get("fecha", ""))
            hora = str(turno.get("hora", "00:00"))
            fecha_str = f"{fecha} {hora}"
            
        dt = parse_fecha_hora(fecha_str)
        
        datos_sql = {
            "paciente_id": pac_uuid,
            "empresa_id": empresa_uuid,
            "fecha_hora_programada": dt.isoformat() if dt else None,
            "estado": turno.get("estado", "Pendiente"),
            "motivo": turno.get("motivo", ""),
            "notas": turno.get("notas", "")
        }
        
        try:
            supabase.table("turnos").insert(datos_sql).execute()
            count_turnos += 1
        except Exception as e:
            print(f"  - Error al migrar turno: {e}")
            
    print(f"  - {count_turnos} turnos migrados exitosamente.")

    # 3. MIGRAR ESTUDIOS MÉDICOS
    print("\nMigrando Estudios Médicos...")
    estudios_db = datos.get("estudios_db", [])
    count_estudios = 0
    
    for est in estudios_db:
        if not isinstance(est, dict): continue
        
        pac_id_viejo = str(est.get("paciente", ""))
        pac_uuid = mapa_pacientes.get(pac_id_viejo)
        
        if not pac_uuid:
            continue
            
        # Parsear fecha
        fecha_str = str(est.get("fecha", ""))
        dt = parse_fecha_hora(fecha_str)
        
        # En la migración, si hay un base64, lo guardamos temporalmente en archivo_url
        # (En el futuro, el código subirá esto al Bucket y guardará la URL real)
        archivo_b64 = est.get("archivo_b64", "")
        if len(archivo_b64) > 50:
            archivo_url = f"base64_legacy:{archivo_b64[:20]}..." # Solo un marcador por ahora
        else:
            archivo_url = ""
            
        datos_sql = {
            "paciente_id": pac_uuid,
            "medico_solicitante": est.get("medico_solicitante", ""),
            "tipo_estudio": est.get("tipo_estudio", ""),
            "fecha_realizacion": dt.date().isoformat() if dt else None,
            "informe": est.get("informe", ""),
            "archivo_url": archivo_url,
            "estado": est.get("estado", "Completado")
        }
        
        try:
            supabase.table("estudios").insert(datos_sql).execute()
            count_estudios += 1
        except Exception as e:
            print(f"  - Error al migrar estudio: {e}")
            
    print(f"  - {count_estudios} estudios migrados exitosamente.")

    print("\n!MIGRACION COMPLETADA CON EXITO!")
    print("Los Turnos y Estudios ahora viven en PostgreSQL.")

if __name__ == "__main__":
    migrar_turnos_estudios()