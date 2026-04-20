"""
SISTEMA DE GUARDADO DE EMERGENCIA
Guarda datos localmente de forma segura mientras se arregla Supabase
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import streamlit as st


def _guardar_supabase_signos_vitales(
    paciente_id: str,
    tension_arterial: str,
    frecuencia_cardiaca: int,
    frecuencia_respiratoria: int,
    temperatura: float,
    saturacion_oxigeno: int,
    glucemia: str,
    observaciones: str = ""
) -> tuple[bool, str]:
    """Guarda en Supabase (nube)."""
    try:
        import streamlit as st
        from supabase import create_client
        
        # Obtener credenciales
        supabase_url = st.secrets.get("SUPABASE_URL", "")
        supabase_key = st.secrets.get("SUPABASE_KEY", "")
        
        if not supabase_url or not supabase_key:
            return False, "Sin credenciales Supabase"
        
        supabase = create_client(supabase_url, supabase_key)
        
        # Buscar paciente_uuid por DNI
        response_paciente = supabase.table('pacientes').select('id').eq('dni', str(paciente_id)).limit(1).execute()
        
        paciente_uuid = None
        if hasattr(response_paciente, 'data') and response_paciente.data:
            paciente_uuid = response_paciente.data[0].get('id')
        
        # Si no existe el paciente, crearlo primero
        if not paciente_uuid:
            nuevo_paciente = {
                "dni": str(paciente_id),
                "nombre": "Paciente " + str(paciente_id),
                "estado": "Activo"
            }
            resp_crear = supabase.table('pacientes').insert(nuevo_paciente).execute()
            if hasattr(resp_crear, 'data') and resp_crear.data:
                paciente_uuid = resp_crear.data[0].get('id')
        
        if not paciente_uuid:
            return False, "No se pudo obtener/crear paciente"
        
        # Insertar signos vitales
        data_sv = {
            "paciente_id": paciente_uuid,
            "tension_arterial": tension_arterial,
            "frecuencia_cardiaca": int(frecuencia_cardiaca) if frecuencia_cardiaca else None,
            "frecuencia_respiratoria": int(frecuencia_respiratoria) if frecuencia_respiratoria else None,
            "temperatura": float(temperatura) if temperatura else None,
            "saturacion_oxigeno": int(saturacion_oxigeno) if saturacion_oxigeno else None,
            "glucemia": str(glucemia) if glucemia else None,
            "observaciones": observaciones
        }
        
        # Limpiar None
        data_sv = {k: v for k, v in data_sv.items() if v is not None}
        
        response = supabase.table('signos_vitales').insert(data_sv).execute()
        
        if hasattr(response, 'data') and response.data:
            return True, "OK Supabase"
        else:
            return False, "Respuesta vacia de Supabase"
            
    except Exception as e:
        return False, f"Error Supabase: {str(e)[:100]}"


def guardar_signos_vitales_local(
    paciente_id: str,
    paciente_nombre: str,
    tension_arterial: str,
    frecuencia_cardiaca: int,
    frecuencia_respiratoria: int,
    temperatura: float,
    saturacion_oxigeno: int,
    glucemia: str,
    observaciones: str = ""
) -> tuple[bool, str]:
    """
    Guarda signos vitales en SUPABASE (nube) + LOCAL (backup).
    Funciona siempre - si Supabase falla, guarda local.
    """
    
    mensajes = []
    supabase_ok = False
    local_ok = False
    
    # 1. INTENTAR GUARDAR EN SUPABASE PRIMERO
    supabase_ok, supabase_msg = _guardar_supabase_signos_vitales(
        paciente_id=paciente_id,
        tension_arterial=tension_arterial,
        frecuencia_cardiaca=frecuencia_cardiaca,
        frecuencia_respiratoria=frecuencia_respiratoria,
        temperatura=temperatura,
        saturacion_oxigeno=saturacion_oxigeno,
        glucemia=glucemia,
        observaciones=observaciones
    )
    
    if supabase_ok:
        mensajes.append("☁️ Guardado en la NUBE (Supabase)")
    else:
        mensajes.append(f"⚠️ Supabase: {supabase_msg}")
    
    # 2. SIEMPRE GUARDAR EN LOCAL COMO BACKUP
    try:
        local_file = Path(".streamlit/local_data.json")
        
        if local_file.exists():
            with open(local_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {
                "pacientes_db": [],
                "vitales_db": [],
                "evoluciones_db": [],
                "recetas_db": [],
                "usuarios_db": []
            }
        
        registro = {
            "id": f"sv_{int(time.time())}",
            "paciente_id": paciente_id,
            "paciente_nombre": paciente_nombre,
            "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "ta": tension_arterial,
            "fc": frecuencia_cardiaca,
            "fr": frecuencia_respiratoria,
            "temp": temperatura,
            "sat": saturacion_oxigeno,
            "hgt": glucemia,
            "observaciones": observaciones,
            "created_at": datetime.now().isoformat(),
            "synced_cloud": supabase_ok
        }
        
        if "vitales_db" not in data:
            data["vitales_db"] = []
        
        data["vitales_db"].append(registro)
        
        with open(local_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        local_ok = True
        mensajes.append("💾 Backup local creado")
        
    except Exception as e:
        mensajes.append(f"❌ Error local: {e}")
    
    # Resultado
    if supabase_ok or local_ok:
        return True, " | ".join(mensajes)
    else:
        return False, " | ".join(mensajes)


def _guardar_supabase_evolucion(paciente_id: str, evolucion: str, indicaciones: str) -> tuple[bool, str]:
    """Guarda evolucion en Supabase."""
    try:
        from supabase import create_client
        
        supabase_url = st.secrets.get("SUPABASE_URL", "")
        supabase_key = st.secrets.get("SUPABASE_KEY", "")
        
        if not supabase_url or not supabase_key:
            return False, "Sin credenciales"
        
        supabase = create_client(supabase_url, supabase_key)
        
        # Buscar paciente_uuid
        response_paciente = supabase.table('pacientes').select('id').eq('dni', str(paciente_id)).limit(1).execute()
        
        paciente_uuid = None
        if hasattr(response_paciente, 'data') and response_paciente.data:
            paciente_uuid = response_paciente.data[0].get('id')
        
        if not paciente_uuid:
            # Crear paciente si no existe
            resp = supabase.table('pacientes').insert({
                "dni": str(paciente_id),
                "nombre": "Paciente " + str(paciente_id),
                "estado": "Activo"
            }).execute()
            if hasattr(resp, 'data') and resp.data:
                paciente_uuid = resp.data[0].get('id')
        
        if not paciente_uuid:
            return False, "No se pudo obtener paciente"
        
        # Insertar evolucion
        data_evo = {
            "paciente_id": paciente_uuid,
            "evolucion": evolucion,
            "indicaciones": indicaciones
        }
        
        response = supabase.table('evoluciones').insert(data_evo).execute()
        
        if hasattr(response, 'data') and response.data:
            return True, "OK Supabase"
        else:
            return False, "Respuesta vacia"
            
    except Exception as e:
        return False, f"Error: {str(e)[:100]}"


def guardar_evolucion_local(
    paciente_id: str,
    paciente_nombre: str,
    evolucion: str,
    indicaciones: str = ""
) -> tuple[bool, str]:
    """Guarda evolución en Supabase + Local (dual)."""
    
    mensajes = []
    supabase_ok = False
    local_ok = False
    
    # 1. Supabase
    supabase_ok, supabase_msg = _guardar_supabase_evolucion(paciente_id, evolucion, indicaciones)
    
    if supabase_ok:
        mensajes.append("☁️ Guardado en NUBE")
    else:
        mensajes.append(f"⚠️ Supabase: {supabase_msg}")
    
    # 2. Local
    try:
        local_file = Path(".streamlit/local_data.json")
        
        if local_file.exists():
            with open(local_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {
                "pacientes_db": [], "vitales_db": [], "evoluciones_db": [],
                "recetas_db": [], "usuarios_db": []
            }
        
        registro = {
            "id": f"ev_{int(time.time())}",
            "paciente_id": paciente_id,
            "paciente_nombre": paciente_nombre,
            "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "evolucion": evolucion,
            "indicaciones": indicaciones,
            "created_at": datetime.now().isoformat(),
            "synced_cloud": supabase_ok
        }
        
        if "evoluciones_db" not in data:
            data["evoluciones_db"] = []
        
        data["evoluciones_db"].append(registro)
        
        with open(local_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        local_ok = True
        mensajes.append("💾 Backup local OK")
        
    except Exception as e:
        mensajes.append(f"❌ Local: {e}")
    
    if supabase_ok or local_ok:
        return True, " | ".join(mensajes)
    else:
        return False, " | ".join(mensajes)


def _obtener_supabase_signos_vitales(paciente_id: str) -> List[Dict]:
    """Obtiene signos vitales de Supabase."""
    try:
        from supabase import create_client
        
        supabase_url = st.secrets.get("SUPABASE_URL", "")
        supabase_key = st.secrets.get("SUPABASE_KEY", "")
        
        if not supabase_url or not supabase_key:
            return []
        
        supabase = create_client(supabase_url, supabase_key)
        
        # Buscar paciente por DNI
        resp_p = supabase.table('pacientes').select('id').eq('dni', str(paciente_id)).limit(1).execute()
        
        if not hasattr(resp_p, 'data') or not resp_p.data:
            return []
        
        paciente_uuid = resp_p.data[0].get('id')
        
        # Obtener signos vitales
        response = supabase.table('signos_vitales').select('*').eq('paciente_id', paciente_uuid).order('fecha_registro', desc=True).limit(100).execute()
        
        if hasattr(response, 'data') and response.data:
            # Convertir a formato local
            resultados = []
            for r in response.data:
                resultados.append({
                    "fecha": r.get('fecha_registro', '')[:16].replace('T', ' '),
                    "ta": r.get('tension_arterial', ''),
                    "fc": r.get('frecuencia_cardiaca', ''),
                    "fr": r.get('frecuencia_respiratoria', ''),
                    "temp": r.get('temperatura', ''),
                    "sat": r.get('saturacion_oxigeno', ''),
                    "hgt": r.get('glucemia', ''),
                    "observaciones": r.get('observaciones', ''),
                    "paciente_id": paciente_id,
                    "fuente": "☁️ Supabase"
                })
            return resultados
        return []
    except Exception as e:
        return []


def obtener_signos_vitales_local(paciente_id: str) -> List[Dict]:
    """Obtiene signos vitales - primero Supabase, luego local."""
    
    # 1. Intentar Supabase primero
    supabase_datos = _obtener_supabase_signos_vitales(paciente_id)
    
    if supabase_datos:
        return supabase_datos
    
    # 2. Fallback a local
    try:
        local_file = Path(".streamlit/local_data.json")
        
        if not local_file.exists():
            return []
        
        with open(local_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        vitales = data.get("vitales_db", [])
        
        # Filtrar por paciente
        return [v for v in vitales if v.get("paciente_id") == paciente_id or v.get("dni") == paciente_id]
        
    except Exception as e:
        try:
            from core.app_logging import log_event
            log_event("guardado_emergencia", f"Error leyendo vitales local: {e}")
        except Exception:
            pass
        return []


def obtener_evoluciones_local(paciente_id: str) -> List[Dict]:
    """Obtiene evoluciones del archivo local."""
    
    try:
        local_file = Path(".streamlit/local_data.json")
        
        if not local_file.exists():
            return []
        
        with open(local_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        evoluciones = data.get("evoluciones_db", [])
        
        return [e for e in evoluciones if e.get("paciente_id") == paciente_id or e.get("dni") == paciente_id]
        
    except Exception as e:
        try:
            from core.app_logging import log_event
            log_event("guardado_emergencia", f"Error leyendo evoluciones local: {e}")
        except Exception:
            pass
        return []
