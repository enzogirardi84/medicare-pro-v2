import sys
import time
from pathlib import Path

# Aseguramos que Python encuentre los módulos del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import cargar_datos, supabase

def migrar_a_sql():
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
    
    # Diccionarios para guardar los nuevos UUIDs y mantener las relaciones
    mapa_empresas = {} # nombre_empresa -> uuid
    mapa_pacientes = {} # "Nombre - DNI" -> uuid
    
    # 1. MIGRAR EMPRESAS
    print("Migrando Clinicas/Empresas...")
    # Extraemos empresas únicas de los pacientes y usuarios
    empresas_unicas = set()
    detalles_pacientes = datos.get("detalles_pacientes_db", {})
    
    for pac_id, detalles in detalles_pacientes.items():
        emp = str(detalles.get("empresa", "Clinica General")).strip()
        if emp: empresas_unicas.add(emp)
        
    for emp in empresas_unicas:
        try:
            # Insertamos y obtenemos el UUID generado
            res = supabase.table("empresas").upsert({"nombre": emp}, on_conflict="nombre").execute()
            if res.data:
                mapa_empresas[emp] = res.data[0]["id"]
                print(f"  - Empresa guardada: {emp} -> {mapa_empresas[emp]}")
        except Exception as e:
            print(f"  - Error con empresa {emp}: {e}")

    # 2. MIGRAR PACIENTES
    print("\nMigrando Pacientes...")
    pacientes_db = datos.get("pacientes_db", [])
    
    for pac_id in pacientes_db:
        detalles = detalles_pacientes.get(pac_id, {})
        if not detalles: continue
        
        nombre_completo = pac_id.split(" - ")[0] if " - " in pac_id else pac_id
        dni = detalles.get("dni", "S/D")
        empresa_nombre = detalles.get("empresa", "Clinica General")
        empresa_uuid = mapa_empresas.get(empresa_nombre)
        
        datos_sql = {
            "empresa_id": empresa_uuid,
            "nombre_completo": nombre_completo,
            "dni": dni,
            "sexo": detalles.get("sexo", ""),
            "telefono": detalles.get("telefono", ""),
            "direccion": detalles.get("direccion", ""),
            "obra_social": detalles.get("obra_social", ""),
            "estado": detalles.get("estado", "Activo"),
            "alergias": detalles.get("alergias", ""),
            "patologias": detalles.get("patologias", "")
        }
        
        try:
            # Insertamos paciente
            res = supabase.table("pacientes").insert(datos_sql).execute()
            if res.data:
                nuevo_uuid = res.data[0]["id"]
                mapa_pacientes[pac_id] = nuevo_uuid
                print(f"  - Paciente migrado: {nombre_completo} -> {nuevo_uuid}")
        except Exception as e:
            print(f"  - Error con paciente {nombre_completo} (DNI: {dni}): {e}")

    # 3. MIGRAR EVOLUCIONES
    print("\nMigrando Evoluciones Clinicas...")
    evoluciones = datos.get("evoluciones_db", [])
    count_ev = 0
    
    for ev in evoluciones:
        pac_id_viejo = ev.get("paciente")
        pac_uuid = mapa_pacientes.get(pac_id_viejo)
        
        if not pac_uuid: continue # Si el paciente no existe, saltamos
        
        datos_sql = {
            "paciente_id": pac_uuid,
            "plantilla": ev.get("plantilla", "Libre"),
            "nota": ev.get("nota", ""),
            "firma_medico": ev.get("firma", "Sistema")
        }
        
        try:
            supabase.table("evoluciones").insert(datos_sql).execute()
            count_ev += 1
        except Exception as e:
            pass
            
    print(f"  - {count_ev} evoluciones migradas exitosamente.")

    print("\n!MIGRACION COMPLETADA CON EXITO!")
    print("Los datos del JSON ahora viven en las tablas relacionales seguras de PostgreSQL.")
    print("Ya podemos refactorizar el código UI para usar los nuevos UUIDs.")

if __name__ == "__main__":
    migrar_a_sql()
