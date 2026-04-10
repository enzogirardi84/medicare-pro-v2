import base64
import json
import re
import urllib.request
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import pytz
import streamlit as st
from PIL import Image

# --- CONFIGURACIÓN GLOBAL ---
ARG_TZ = pytz.timezone("America/Argentina/Buenos_Aires")
BASE_PATH = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_PATH / "assets"

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

ROLE_LEVELS = {
    "Operativo": 1,
    "Coordinador / Administrativo": 2,
    "Admin": 3,
}

# --- MOTOR DE PERMISOS ---

def tiene_permiso(rol_actual: str, roles_permitidos: Optional[List[str]] = None) -> bool:
    if rol_actual == "Admin": return True
    if not roles_permitidos: return True
    nivel_actual = ROLE_LEVELS.get(rol_actual, 0)
    niveles_v = [ROLE_LEVELS.get(r, 99) for r in roles_permitidos]
    return nivel_actual >= min(niveles_v) if niveles_v else True

def obtener_modulos_permitidos(rol: str) -> List[str]:
    """Define qué módulos ve cada grupo."""
    modulos_atencion = [
        "Visitas y Agenda", "Clinica", "Pediatria", "Evolucion", "Estudios",
        "Materiales", "Recetas", "Balance", "Emergencias y Ambulancia",
        "Escalas Clinicas", "Historial", "PDF", "Telemedicina"
    ]
    modulos_gestion = [
        "Dashboard", "Admision", "Inventario", "Caja", "Red de Profesionales",
        "Cierre Diario", "Mi Equipo", "Asistencia en Vivo", "RRHH y Fichajes",
        "Auditoria", "Auditoria Legal"
    ]
    if rol in ["Admin", "Coordinador / Administrativo"]:
        return modulos_atencion + modulos_gestion
    return modulos_atencion if rol == "Operativo" else []

def puede_accion(rol_actual: str, accion: str) -> bool:
    return tiene_permiso(rol_actual, ["Operativo"])

def descripcion_acceso_rol(rol_actual: str) -> str:
    desc = {
        "Admin": "Control total del sistema, bases de datos y usuarios.",
        "Coordinador / Administrativo": "Acceso completo a gestión operativa, contable y clínica.",
        "Operativo": "Acceso restringido a la atención directa y registro del paciente.",
    }
    return desc.get(rol_actual, "Rol no configurado.")

# --- MANEJO DE ASSETS Y ARCHIVOS ---

@st.cache_data(show_spinner=False)
def cargar_texto_asset(nombre_archivo: str) -> str:
    ruta = ASSETS_DIR / nombre_archivo
    if ruta.exists():
        return ruta.read_text(encoding="utf-8")
    return ""

def es_control_total(rol_actual: str) -> bool:
    return rol_actual in {"Admin", "Coordinador / Administrativo"}

# --- UTILIDADES DE DATOS Y PACIENTES ---

def filtrar_registros_empresa(items, mi_empresa, rol_actual, empresa_key="empresa"):
    if es_control_total(rol_actual): return list(items or [])
    empresa_actual = str(mi_empresa or "").strip().lower()
    return [i for i in (items or []) if str(i.get(empresa_key, "")).strip().lower() == empresa_actual]

def compactar_etiqueta_paciente(nombre: str, estado: str) -> str:
    nombre = str(nombre or "").strip()
    tag = " [ALTA]" if estado == "De Alta" else ""
    return f"{nombre[:27]}..." if len(nombre) > 30 else f"{nombre}{tag}"

def obtener_pacientes_visibles(session_state: Any, mi_empresa: str, rol_actual: str, 
                               incluir_altas: bool = False, busqueda: str = "") -> List[Tuple]:
    busqueda_norm = busqueda.strip().lower()
    detalles_db = session_state.get("detalles_pacientes_db", {})
    visibles = []
    for p_id in session_state.get("pacientes_db", []):
        det = detalles_db.get(p_id, {})
        if not es_control_total(rol_actual):
            if str(det.get("empresa", "")).lower() != str(mi_empresa).lower(): continue
        estado = det.get("estado", "Activo")
        if estado != "Activo" and not incluir_altas: continue
        if busqueda_norm and busqueda_norm not in f"{p_id} {det.get('dni','')}".lower(): continue
        visibles.append((p_id, compactar_etiqueta_paciente(p_id, estado), det.get("dni",""), 
                         det.get("obra_social",""), estado, det.get("empresa","")))
    return sorted(visibles, key=lambda x: x[1].lower())

def obtener_alertas_clinicas(session_state, paciente_sel):
    if not paciente_sel: return []
    det = session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
    alertas = []
    if alg := str(det.get("alergias", "")).strip():
        alertas.append({"nivel": "critica", "titulo": "Alergias", "detalle": alg})
    return alertas

# --- INICIALIZACIÓN ---

def asegurar_usuarios_base():
    """Garantiza la existencia del Admin."""
    st.session_state.setdefault("usuarios_db", {})
    if "admin" not in st.session_state["usuarios_db"]:
        st.session_state["usuarios_db"]["admin"] = DEFAULT_ADMIN_USER.copy()

def inicializar_db_state(db: Optional[Dict]):
    if "db_inicializada" not in st.session_state:
        # Estructuras de datos base
        for c in ["pacientes_db", "vitales_db", "indicaciones_db", "evoluciones_db", 
                  "auditoria_legal_db", "consumos_db", "emergencias_db", "estudios_db"]:
            st.session_state.setdefault(c, [])
        for c in ["usuarios_db", "detalles_pacientes_db"]:
            st.session_state.setdefault(c, {})

        if db:
            for k, v in db.items(): st.session_state[k] = v
        
        asegurar_usuarios_base()
        st.session_state["db_inicializada"] = True

# --- TIEMPO Y AUDITORÍA ---

def ahora() -> datetime:
    return datetime.now(ARG_TZ)

def registrar_auditoria_legal(tipo_evento, paciente, accion, actor, matricula="", detalle="", referencia="", extra=None, empresa=None):
    st.session_state.setdefault("auditoria_legal_db", [])
    st.session_state["auditoria_legal_db"].append({
        "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
        "tipo_evento": tipo_evento, "paciente": paciente, "accion": accion,
        "actor": actor, "detalle": detalle, "empresa": empresa or "SISTEMA"
    })

# --- IMÁGENES Y FIRMAS ---

def optimizar_imagen_bytes(image_bytes: bytes, max_size=(1280, 1280), quality=70) -> Tuple[bytes, str]:
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            if img.mode != "RGB": img = img.convert("RGB")
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", optimize=True, quality=quality)
            return buf.getvalue(), "jpg"
    except: return image_bytes, "bin"

def firma_a_base64(canvas_image_data=None, uploaded_file=None) -> str:
    try:
        if uploaded_file:
            img_bytes, _ = optimizar_imagen_bytes(uploaded_file.getvalue(), (600, 200), 50)
            return base64.b64encode(img_bytes).decode()
        if canvas_image_data is not None:
            img = Image.fromarray(canvas_image_data.astype("uint8"), "RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3]) 
            buf = BytesIO(); bg.save(buf, format="JPEG", quality=50)
            return base64.b64encode(buf.getvalue()).decode()
    except: return ""
    return ""

def seleccionar_limite_registros(label, total, key, default=30):
    ops = sorted({10, 20, 30, 50, 100} | {total})
    return st.selectbox(label, [v for v in ops if v <= total], key=key)
