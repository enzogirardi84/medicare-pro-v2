import sys
import time
from pathlib import Path

# Aseguramos que Python encuentre los módulos del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.database import cargar_datos, supabase
from core.utils import parse_fecha_hora

def migrar_gestion():
    if not supabase:
        print("❌ Error: No hay conexión a Supabase configurada.")
        return

    print("Cargando datos del JSON actual...")
    datos = cargar_datos(force=True, monolito_legacy=True)
    if not datos:
        print("❌ No se encontraron datos locales para migrar.")
        return

    print("Datos JSON cargados. Iniciando migracion a PostgreSQL...\n")
    
    # 1. Obtener mapas de UUIDs existentes
    print("Obteniendo UUIDs de empresas, pacientes y usuarios...")
    mapa_empresas = {}
    res_emp = supabase.table("empresas").select("id, nombre").execute()
    for emp in res_emp.data:
        mapa_empresas[emp["nombre"]] = emp["id"]
        
    mapa_pacientes = {}
    res_pac = supabase.table("pacientes").select("id, nombre_completo, dni").execute()
    for pac in res_pac.data:
        clave = f"{pac['nombre_completo']} - {pac['dni']}"
        mapa_pacientes[clave] = pac["id"]

    mapa_usuarios = {}
    res_usr = supabase.table("usuarios").select("id, nombre").execute()
    for usr in res_usr.data:
        mapa_usuarios[usr["nombre"]] = usr["id"]

    # Helpers
    def _to_float(val):
        try: return float(str(val).replace(",", ".").strip())
        except: return 0.0
        
    def _to_int(val):
        try: return int(float(str(val).strip()))
        except: return 0

    # 2. MIGRAR INVENTARIO
    print("\nMigrando Inventario...")
    inventario_db = datos.get("inventario_db", [])
    count_inv = 0
    
    for inv in inventario_db:
        if not isinstance(inv, dict): continue
        
        emp_uuid = mapa_empresas.get(str(inv.get("empresa", "")))
        if not emp_uuid: continue
            
        datos_sql = {
            "empresa_id": emp_uuid,
            "codigo": str(inv.get("codigo", ""))[:50],
            "nombre": str(inv.get("nombre", "Sin Nombre"))[:255],
            "categoria": str(inv.get("categoria", ""))[:100],
            "stock_actual": _to_int(inv.get("stock", 0)),
            "stock_minimo": _to_int(inv.get("stock_minimo", 0)),
            "unidad_medida": str(inv.get("unidad", ""))[:50],
            "costo_unitario": _to_float(inv.get("costo", 0)),
            "precio_venta": _to_float(inv.get("precio", 0)),
            "observaciones": str(inv.get("observaciones", ""))
        }
        
        try:
            supabase.table("inventario").insert(datos_sql).execute()
            count_inv += 1
        except Exception as e:
            print(f"  - Error al migrar inventario: {e}")
            
    print(f"  - {count_inv} items de inventario migrados exitosamente.")

    # 3. MIGRAR FACTURACION
    print("\nMigrando Facturación...")
    facturacion_db = datos.get("facturacion_db", [])
    count_fac = 0
    
    for fac in facturacion_db:
        if not isinstance(fac, dict): continue
        
        emp_uuid = mapa_empresas.get(str(fac.get("empresa", "")))
        if not emp_uuid: continue
            
        pac_uuid = None
        pac_nombre = str(fac.get("paciente", ""))
        if pac_nombre and pac_nombre != "N/A":
            pac_uuid = mapa_pacientes.get(pac_nombre)
            
        dt = parse_fecha_hora(str(fac.get("fecha", "")))
        
        datos_sql = {
            "empresa_id": emp_uuid,
            "paciente_id": pac_uuid,
            "fecha_emision": dt.isoformat() if dt else None,
            "numero_comprobante": str(fac.get("comprobante", ""))[:100],
            "concepto": str(fac.get("concepto", "Facturación")),
            "monto_total": _to_float(fac.get("monto", fac.get("total", 0))),
            "estado": str(fac.get("estado", "Pendiente"))[:50],
            "obra_social": str(fac.get("obra_social", ""))[:255],
            "observaciones": str(fac.get("observaciones", ""))
        }
        
        try:
            supabase.table("facturacion").insert(datos_sql).execute()
            count_fac += 1
        except Exception as e:
            print(f"  - Error al migrar facturación: {e}")
            
    print(f"  - {count_fac} registros de facturación migrados exitosamente.")

    # 4. MIGRAR BALANCE
    print("\nMigrando Balance...")
    balance_db = datos.get("balance_db", [])
    count_bal = 0
    
    for bal in balance_db:
        if not isinstance(bal, dict): continue
        
        emp_uuid = mapa_empresas.get(str(bal.get("empresa", "")))
        if not emp_uuid: continue
            
        dt = parse_fecha_hora(str(bal.get("fecha", "")))
        
        datos_sql = {
            "empresa_id": emp_uuid,
            "fecha_movimiento": dt.isoformat() if dt else None,
            "tipo_movimiento": str(bal.get("tipo", "Ingreso"))[:20],
            "categoria": str(bal.get("categoria", ""))[:100],
            "concepto": str(bal.get("concepto", "Movimiento")),
            "monto": _to_float(bal.get("monto", bal.get("importe", 0))),
            "comprobante": str(bal.get("comprobante", ""))[:100],
            "observaciones": str(bal.get("observaciones", ""))
        }
        
        try:
            supabase.table("balance").insert(datos_sql).execute()
            count_bal += 1
        except Exception as e:
            print(f"  - Error al migrar balance: {e}")
            
    print(f"  - {count_bal} registros de balance migrados exitosamente.")

    # 5. MIGRAR CHECK-IN (RRHH)
    print("\nMigrando Check-in / Asistencia...")
    checkin_db = datos.get("checkin_db", [])
    count_chk = 0
    
    for chk in checkin_db:
        if not isinstance(chk, dict): continue
        
        emp_uuid = mapa_empresas.get(str(chk.get("empresa", "")))
        if not emp_uuid: continue
            
        pac_uuid = None
        pac_nombre = str(chk.get("paciente", ""))
        if pac_nombre and pac_nombre != "N/A" and pac_nombre != "-":
            pac_uuid = mapa_pacientes.get(pac_nombre)
            
        usr_uuid = mapa_usuarios.get(str(chk.get("profesional", "")))
            
        dt = parse_fecha_hora(str(chk.get("fecha_hora", "")))
        
        # Extraer lat/lon si existe
        lat, lon = None, None
        gps = str(chk.get("gps", ""))
        if "," in gps:
            try:
                partes = gps.split(",")
                lat = float(partes[0].strip())
                lon = float(partes[1].strip())
            except:
                pass
        
        datos_sql = {
            "empresa_id": emp_uuid,
            "usuario_id": usr_uuid,
            "paciente_id": pac_uuid,
            "fecha_hora": dt.isoformat() if dt else None,
            "tipo_registro": str(chk.get("tipo", "REGISTRO"))[:50],
            "latitud": lat,
            "longitud": lon,
            "direccion_estimada": str(chk.get("direccion", "")),
            "observaciones": str(chk.get("observaciones", ""))
        }
        
        try:
            supabase.table("checkin_asistencia").insert(datos_sql).execute()
            count_chk += 1
        except Exception as e:
            print(f"  - Error al migrar check-in: {e}")
            
    print(f"  - {count_chk} registros de check-in migrados exitosamente.")

    print("\n!MIGRACION COMPLETADA CON EXITO!")

if __name__ == "__main__":
    migrar_gestion()