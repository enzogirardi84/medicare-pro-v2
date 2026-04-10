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
# Mejora en la definición de rutas para evitar errores de despliegue
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
    """Evalúa permisos por jerarquía de niveles."""
    if rol_actual == "Admin":
        return True
    if not roles_permitidos:
        return True
    if rol_actual in roles_permitidos:
        return True
    
    # Lógica de niveles: si el rol actual tiene un nivel >= al mínimo requerido
    nivel_actual = ROLE_LEVELS.get(rol_actual, 0)
    niveles_validos = [ROLE_LEVELS.get(r, 99) for r in roles_permitidos]
    nivel_minimo = min(niveles_validos) if niveles_validos else 99
    
    return nivel_actual >= nivel_minimo

def obtener_modulos_permitidos(rol: str) -> List[str]:
    """Retorna los módulos accesibles según el grupo de usuario."""
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
    
    if rol == "Operativo":
        return modulos_atencion
        
    return []

# --- MANEJO DE ARCHIVOS Y ASSETS ---

@st.cache_data(show_spinner=False)
def cargar_texto_asset(nombre_archivo: str) -> str:
    """Carga archivos de texto (CSS/JS) con manejo de errores."""
    ruta = ASSETS_DIR / nombre_archivo
    try:
        if ruta.exists():
            return ruta.read_text(encoding="utf-8")
    except Exception as e:
        st.error(f"Error cargando asset {nombre_archivo}: {e}")
    return ""

# --- UTILIDADES CLÍNICAS Y DE DATOS ---

def filtrar_registros_empresa(items: List[Dict], mi_empresa: str, rol_actual: str, empresa_key: str = "empresa") -> List[Dict]:
    """Filtra datos según la empresa del usuario, a menos que sea Admin."""
    if rol_actual in ["Admin", "Coordinador / Administrativo"]:
        return list(items or [])
    
    empresa_target = str(mi_empresa or "").strip().lower()
    return [i for i in (items or []) if str(i.get(empresa_key, "")).strip().lower() == empresa_target]

def compactar_etiqueta_paciente(nombre: str, estado: str) -> str:
    """Formatea el nombre del paciente para la UI."""
    nombre = str(nombre or "").strip()
    tag = " [ALTA]" if estado == "De Alta" else ""
    limite = 30
    return f"{nombre[:limite]}..." if len(nombre) > limite else f"{nombre}{tag}"

def obtener_pacientes_visibles(session_state: Any, mi_empresa: str, rol_actual: str, 
                               incluir_altas: bool = False, busqueda: str = "") -> List[Tuple]:
    """Genera lista de pacientes filtrada por permisos y búsqueda."""
    busqueda_norm = busqueda.strip().lower()
    detalles_db = session_state.get("detalles_pacientes_db", {})
    visibles = []
    
    for paciente_id in session_state.get("pacientes_db", []):
        det = detalles_db.get(paciente_id, {})
        
        # Filtro de empresa
        if rol_actual not in ["Admin", "Coordinador / Administrativo"]:
            if str(det.get("empresa", "")).lower() != str(mi_empresa).lower():
                continue
        
        # Filtro de estado
        estado = det.get("estado", "Activo")
        if estado != "Activo" and not incluir_altas:
            continue
            
        # Filtro de búsqueda
        dni = str(det.get("dni", ""))
        if busqueda_norm and busqueda_norm not in f"{paciente_id} {dni}".lower():
            continue
            
        visibles.append((
            paciente_id, 
            compactar_etiqueta_paciente(paciente_id, estado), 
            dni, 
            det.get("obra_social", ""), 
            estado, 
            det.get("empresa", "")
        ))
    
    return sorted(visibles, key=lambda x: x[1].lower())

# --- AUDITORÍA Y TIEMPO ---

def ahora() -> datetime:
    """Retorna fecha y hora actual en zona horaria Argentina."""
    return datetime.now(ARG_TZ)

def registrar_auditoria_legal(tipo_evento: str, paciente: str, accion: str, actor: str, 
                             matricula: str = "", detalle: str = "", referencia: str = "", 
                             extra: Dict = None, empresa: str = None):
    """Registra eventos en el log de auditoría."""
    st.session_state.setdefault("auditoria_legal_db", [])
    
    # Intentar obtener empresa si no se provee
    if not empresa:
        u_actual = st.session_state.get("u_actual", {})
        empresa = u_actual.get("empresa", "SISTEMA")

    st.session_state["auditoria_legal_db"].append({
        "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
        "tipo_evento": tipo_evento,
        "paciente": paciente,
        "accion": accion,
        "actor": actor,
        "matricula": matricula,
        "detalle": detalle,
        "referencia": referencia,
        "empresa": empresa,
        **(extra or {})
    })

# --- PROCESAMIENTO DE IMÁGENES Y FIRMAS ---

def optimizar_imagen_bytes(image_bytes: bytes, max_size: Tuple[int, int] = (1280, 1280), 
                          quality: int = 70) -> Tuple[bytes, str]:
    """Reduce el peso de las imágenes para ahorrar espacio en DB."""
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", optimize=True, quality=quality)
            return buf.getvalue(), "jpg"
    except Exception as e:
        return image_bytes, "bin"

def firma_a_base64(canvas_image_data: Any = None, uploaded_file: Any = None) -> str:
    """Convierte firma (dibujada o subida) a string Base64 optimizado."""
    try:
        if uploaded_file:
            img_bytes, _ = optimizar_imagen_bytes(uploaded_file.getvalue(), (600, 200), 50)
            return base64.b64encode(img_bytes).decode()
        
        if canvas_image_data is not None:
            img = Image.fromarray(canvas_image_data.astype("uint8"), "RGBA")
            # Crear fondo blanco para firmas transparentes (evita fondos negros en PDF)
            fondo_blanco = Image.new("RGB", img.size, (255, 255, 255))
            fondo_blanco.paste(img, mask=img.split()[3]) 
            fondo_blanco.thumbnail((600, 200))
            buf = BytesIO()
            fondo_blanco.save(buf, format="JPEG", quality=50)
            return base64.b64encode(buf.getvalue()).decode()
    except:
        return ""
    return ""

# --- INICIALIZACIÓN ---

def inicializar_db_state(db: Optional[Dict]):
    """Carga la base de datos en el estado de la sesión."""
    if "db_inicializada" not in st.session_state:
        # Estructura base de datos
        claves_listas = [
            "pacientes_db", "vitales_db", "indicaciones_db", "evoluciones_db", 
            "auditoria_legal_db", "consumos_db", "emergencias_db", "estudios_db", 
            "balance_db", "pediatria_db", "fotos_heridas_db"
        ]
        claves_dict = ["usuarios_db", "detalles_pacientes_db"]

        for c in claves_listas: st.session_state.setdefault(c, [])
        for c in claves_dict: st.session_state.setdefault(c, {})

        if db:
            for k, v in db.items():
                st.session_state[k] = v
        
        # Asegurar usuario administrador
        if "admin" not in st.session_state["usuarios_db"]:
            st.session_state["usuarios_db"]["admin"] = DEFAULT_ADMIN_USER.copy()
            
        st.session_state["db_inicializada"] = True
