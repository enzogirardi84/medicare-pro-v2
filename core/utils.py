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

# ====================== CONFIGURACIÓN GLOBAL ======================
ARG_TZ = pytz.timezone("America/Argentina/Buenos_Aires")
BASE_PATH = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_PATH / "assets"

# Usuario maestro de recuperación (SuperAdmin)
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

# ====================== MOTOR DE PERMISOS ======================
def obtener_modulos_permitidos(rol: str) -> List[str]:
    """Retorna los módulos visibles según el rol."""
    r = str(rol or "").strip().lower()
    atencion = [
        "Visitas y Agenda", "Clinica", "Pediatria", "Evolucion", "Estudios",
        "Materiales", "Recetas", "Balance", "Emergencias y Ambulancia",
        "Escalas Clinicas", "Historial", "PDF", "Telemedicina"
    ]
    gestion = [
        "Dashboard", "Admision", "Inventario", "Caja", "Red de Profesionales",
        "Cierre Diario", "Mi Equipo", "Asistencia en Vivo", "RRHH y Fichajes",
        "Auditoria", "Auditoria Legal"
    ]

    if any(k in r for k in ["admin", "coord", "geren", "sistemas"]):
        return atencion + gestion
    if "operativo" in r:
        return atencion
    return ["Visitas y Agenda", "Clinica", "Evolucion"]


def descripcion_acceso_rol(rol: str) -> str:
    r = str(rol or "").strip().lower()
    return "Control total de infraestructura y seguridad clínica." if any(k in r for k in ["admin", "coord"]) else "Acceso asistencial restringido a atención directa."


def es_control_total(rol: str) -> bool:
    r = str(rol or "").strip().lower()
    return any(k in r for k in ["admin", "coord", "geren", "sistemas"])


def tiene_permiso(rol_actual: str, roles_permitidos: Optional[List[str]] = None) -> bool:
    if not roles_permitidos:
        return True
    r = str(rol_actual).lower()
    if "admin" in r:
        return True
    return any(rp.lower() in r for rp in roles_permitidos)


# ====================== UTILIDADES DE SISTEMA ======================
@st.cache_data(show_spinner=False)
def cargar_texto_asset(nombre: str) -> str:
    """Carga archivos de texto desde la carpeta assets."""
    ruta = ASSETS_DIR / nombre
    try:
        return ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    except Exception:
        return ""


def ahora() -> datetime:
    """Fecha y hora actual en Argentina."""
    return datetime.now(ARG_TZ)


# ====================== MANEJO DE PACIENTES ======================
def compactar_etiqueta_paciente(nombre: str, estado: str) -> str:
    """Corta el nombre y agrega etiqueta de alta si corresponde."""
    nombre = str(nombre or "").strip()
    tag = " [ALTA]" if estado == "De Alta" else ""
    return f"{nombre[:25]}..." if len(nombre) > 28 else f"{nombre}{tag}"


def obtener_pacientes_visibles(
    session_state,
    mi_empresa: str,
    rol: str,
    incluir_altas: bool = False,
    busqueda: str = ""
) -> List[Tuple]:
    """Devuelve lista de pacientes visibles según permisos y búsqueda."""
    busqueda_norm = str(busqueda or "").strip().lower()
    detalles_db = session_state.get("detalles_pacientes_db", {})
    visibles = []

    for p_id in session_state.get("pacientes_db", []):
        det = detalles_db.get(p_id, {})
        if not es_control_total(rol):
            if str(det.get("empresa", "")).lower() != str(mi_empresa).lower():
                continue

        estado = det.get("estado", "Activo")
        if estado != "Activo" and not incluir_altas:
            continue

        if busqueda_norm and busqueda_norm not in f"{p_id} {det.get('dni','')}".lower():
            continue

        visibles.append((
            p_id,
            compactar_etiqueta_paciente(p_id, estado),
            det.get("dni", ""),
            det.get("obra_social", ""),
            estado,
            det.get("empresa", "")
        ))

    return sorted(visibles, key=lambda x: x[1].lower())


def obtener_alertas_clinicas(session_state, paciente_sel: Optional[str]):
    """Retorna alertas clínicas del paciente seleccionado."""
    if not paciente_sel:
        return []
    det = session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
    alertas = []
    if alg := str(det.get("alergias", "")).strip():
        alertas.append({"nivel": "critica", "titulo": "Alergias", "detalle": alg})
    return alertas


# ====================== INICIALIZACIÓN DE BASE DE DATOS ======================
def asegurar_usuarios_base():
    """Garantiza que el usuario admin siempre exista."""
    if "usuarios_db" not in st.session_state:
        st.session_state["usuarios_db"] = {}
    if "admin" not in st.session_state["usuarios_db"]:
        st.session_state["usuarios_db"]["admin"] = DEFAULT_ADMIN_USER.copy()


def inicializar_db_state(db: Optional[Dict] = None):
    """Inicializa todas las colecciones de la base de datos en session_state."""
    if "db_inicializada" not in st.session_state:
        listas = [
            "pacientes_db", "vitales_db", "indicaciones_db", "evoluciones_db",
            "auditoria_legal_db", "consumos_db", "emergencias_db", "estudios_db"
        ]
        dicts = ["usuarios_db", "detalles_pacientes_db"]

        for c in listas:
            st.session_state.setdefault(c, [])
        for c in dicts:
            st.session_state.setdefault(c, {})

        if db:
            for k, v in db.items():
                st.session_state[k] = v

        asegurar_usuarios_base()
        st.session_state["db_inicializada"] = True


# ====================== MULTIMEDIA ======================
def firma_a_base64(canvas_image_data=None, uploaded_file=None) -> str:
    """Convierte firma digital o imagen a base64."""
    try:
        if uploaded_file:
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
    except Exception:
        return ""
    return ""


def registrar_auditoria_legal(
    tipo_evento: str,
    paciente: str,
    accion: str,
    actor: str,
    detalle: str = "",
    empresa: Optional[str] = None
):
    """Registra evento en la auditoría legal."""
    st.session_state.setdefault("auditoria_legal_db", [])
    st.session_state["auditoria_legal_db"].append({
        "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
        "tipo_evento": tipo_evento,
        "paciente": paciente,
        "accion": accion,
        "actor": actor,
        "detalle": detalle,
        "empresa": empresa or "SISTEMA"
    })


# ====================== UTILIDADES VISUALES (usadas por múltiples vistas) ======================
def mostrar_dataframe_con_scroll(df, height: int = 500, key: Optional[str] = None):
    """Muestra DataFrame con scroll y mejor presentación."""
    import pandas as pd
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        st.info("ℹ️ No hay registros para mostrar")
        return
    st.dataframe(
        df,
        use_container_width=True,
        height=height,
        key=key,
        hide_index=False
    )


def seleccionar_limite_registros(default: int = 50) -> int:
    """Selectbox para elegir cantidad de registros a mostrar."""
    import streamlit as st
    opciones = [10, 20, 50, 100, 200, 500, 1000]
    idx = 3  # default 50
    if default in opciones:
        idx = opciones.index(default)
    return st.selectbox(
        "Cantidad de registros a mostrar",
        options=opciones,
        index=idx,
        key="limite_registros_general"
    )
