import base64
import json
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import pytz
import streamlit as st
from PIL import Image

# --- 1. CONFIGURACIÓN Y RUTAS ---
ARG_TZ = pytz.timezone("America/Argentina/Buenos_Aires")
BASE_PATH = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_PATH / "assets"

# Usuario maestro de recuperación
DEFAULT_ADMIN_USER = {
    "pass": "37108100",
    "rol": "Admin",
    "nombre": "Enzo Girardi",
    "empresa": "SISTEMAS E.G.",
    "matricula": "M.P 21947",
    "dni": "37108100",
    "titulo": "Director de Sistemas",
    "estado": "Activo",
    "pin": "1234",
}

# --- 2. MOTOR DE PERMISOS (VERSIÓN ULTRA-FLEXIBLE) ---

def obtener_modulos_permitidos(rol: str) -> List[str]:
    """
    Retorna los módulos visibles según el rol.
    Ahora usa búsqueda de palabras clave para evitar bloqueos por nombres de rol.
    """
    r = str(rol or "").strip().lower()

    # Módulos base de atención (Nivel Operativo)
    atencion = [
        "Visitas y Agenda", "Clinica", "Pediatria", "Evolucion", "Estudios",
        "Materiales", "Recetas", "Balance", "Emergencias y Ambulancia",
        "Escalas Clinicas", "Historial", "PDF", "Telemedicina"
    ]
    
    # Módulos de administración (Nivel Gerencial)
    gestion = [
        "Dashboard", "Admision", "Inventario", "Caja", "Red de Profesionales",
        "Cierre Diario", "Mi Equipo", "Asistencia en Vivo", "RRHH y Fichajes",
        "Auditoria", "Auditoria Legal"
    ]

    # Lógica de asignación flexible
    if any(keyword in r for keyword in ["admin", "coord", "geren", "sistemas"]):
        return atencion + gestion
    
    if "operativo" in r or "enfermero" in r or "medico" in r:
        return atencion
        
    # Retorno de emergencia (para que nunca quede la pantalla en blanco)
    return ["Visitas y Agenda", "Clinica", "Evolucion"]

def descripcion_acceso_rol(rol: str) -> str:
    r = str(rol or "").strip().lower()
    if "admin" in r: return "Control total de infraestructura y seguridad."
    if "coord" in r: return "Gestión operativa y administrativa completa."
    return "Acceso asistencial restringido."

def es_control_total(rol: str) -> bool:
    r = str(rol or "").strip().lower()
    return any(keyword in r for keyword in ["admin", "coord", "geren"])

# --- 3. UTILIDADES DE SISTEMA ---

@st.cache_data(show_spinner=False)
def cargar_texto_asset(nombre: str) -> str:
    ruta = ASSETS_DIR / nombre
    try:
        return ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    except: return ""

def ahora() -> datetime:
    return datetime.now(ARG_TZ)

# --- 4. MANEJO DE PACIENTES ---

def compactar_etiqueta_paciente(nombre: str, estado: str) -> str:
    nombre = str(nombre or "").strip()
    tag = " [ALTA]" if estado == "De Alta" else ""
    return f"{nombre[:25]}..." if len(nombre) > 28 else f"{nombre}{tag}"

def obtener_pacientes_visibles(session_state, mi_empresa, rol, incluir_altas=False, busqueda=""):
    busqueda_norm = str(busqueda or "").strip().lower()
    detalles_db = session_state.get("detalles_pacientes_db", {})
    visibles = []
    
    for p_id in session_state.get("pacientes_db", []):
        det = detalles_db.get(p_id, {})
        
        # Filtro de empresa (Los admins ven todo)
        if not es_control_total(rol):
            if str(det.get("empresa", "")).lower() != str(mi_empresa).lower():
                continue
        
        estado = det.get("estado", "Activo")
        if estado != "Activo" and not incluir_altas: continue
        
        if busqueda_norm and busqueda_norm not in f"{p_id} {det.get('dni','')}".lower():
            continue
            
        visibles.append((p_id, compactar_etiqueta_paciente(p_id, estado), det.get("dni",""), 
                         det.get("obra_social",""), estado, det.get("empresa","")))
    
    return sorted(visibles, key=lambda x: x[1].lower())

# --- 5. INICIALIZACIÓN DE BASE DE DATOS ---

def inicializar_db_state(db: Optional[Dict]):
    """Garantiza que todas las tablas existan en la sesión."""
    if "db_inicializada" not in st.session_state:
        listas = ["pacientes_db", "vitales_db", "indicaciones_db", "evoluciones_db", 
                  "auditoria_legal_db", "consumos_db", "emergencias_db", "estudios_db", 
                  "balance_db", "pediatria_db", "fotos_heridas_db"]
        dicts = ["usuarios_db", "detalles_pacientes_db"]

        for c in listas: st.session_state.setdefault(c, [])
        for c in dicts: st.session_state.setdefault(c, {})

        if db:
            for k, v in db.items(): st.session_state[k] = v
        
        # Asegurar usuario Admin de rescate
        if "admin" not in st.session_state["usuarios_db"]:
            st.session_state["usuarios_db"]["admin"] = DEFAULT_ADMIN_USER.copy()
            
        st.session_state["db_inicializada"] = True

# --- 6. FIRMAS Y MULTIMEDIA ---

def firma_a_base64(canvas_image_data=None, uploaded_file=None) -> str:
    try:
        if uploaded_file:
            # Reducimos peso drásticamente para Supabase/DB
            with Image.open(uploaded_file) as img:
                img.thumbnail((600, 200))
                buf = BytesIO()
                img.convert("RGB").save(buf, format="JPEG", quality=50)
                return base64.b64encode(buf.getvalue()).decode()
        
        if canvas_image_data is not None:
            img = Image.fromarray(canvas_image_data.astype("uint8"), "RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3]) 
            bg.thumbnail((600, 200))
            buf = BytesIO()
            bg.save(buf, format="JPEG", quality=50)
            return base64.b64encode(buf.getvalue()).decode()
    except: return ""
    return ""

def registrar_auditoria_legal(tipo_evento, paciente, accion, actor, detalle="", empresa=None):
    st.session_state.setdefault("auditoria_legal_db", [])
    st.session_state["auditoria_legal_db"].append({
        "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
        "tipo_evento": tipo_evento, "paciente": paciente, "accion": accion,
        "actor": actor, "detalle": detalle, "empresa": empresa or "SISTEMA"
    })
