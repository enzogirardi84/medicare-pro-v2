import base64
import json
import re
import urllib.request
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pytz
import streamlit as st
from PIL import Image

# Zona horaria fija para Argentina
ARG_TZ = pytz.timezone("America/Argentina/Buenos_Aires")
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

# --- USUARIO POR DEFECTO ACTUALIZADO ---
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

# --- ESTRUCTURA DE ROLES SIMPLIFICADA (NIVELES) ---
ROLE_LEVELS = {
    "Operativo": 1,
    "Coordinador / Administrativo": 2,
    "Admin": 3,
}

# Reglas de acciones específicas
ACTION_ROLE_RULES = {
    "recetas_prescribir": ["Operativo"],
    "recetas_cargar_papel": ["Operativo"],
    "recetas_registrar_dosis": ["Operativo"],
    "recetas_cambiar_estado": ["Operativo"],
    "pdf_exportar_historia": ["Operativo"],
    "pdf_exportar_excel": ["Coordinador / Administrativo"],
    "pdf_exportar_respaldo": ["Operativo"],
    "pdf_guardar_consentimiento": ["Operativo"],
    "pdf_descargar_consentimiento": ["Operativo"],
    "evolucion_registrar": ["Operativo"],
    "evolucion_borrar": ["Operativo"], 
    "estudios_registrar": ["Operativo"],
    "estudios_borrar": ["Operativo"],
    "equipo_crear_usuario": ["Coordinador / Administrativo"],
    "equipo_cambiar_estado": ["Coordinador / Administrativo"],
    "equipo_eliminar_usuario": ["Admin"],
}

# --- FUNCIONES DE ACCESO Y PERMISOS ---

def tiene_permiso(rol_actual, roles_permitidos=None):
    """Evalúa permisos por jerarquía: Niveles superiores heredan permisos de inferiores."""
    if rol_actual == "Admin":
        return True
    if not roles_permitidos:
        return True
    if rol_actual in roles_permitidos:
        return True
    
    nivel_actual = ROLE_LEVELS.get(rol_actual, 0)
    # Buscamos el nivel mínimo de los roles permitidos
    roles_validos = [ROLE_LEVELS.get(r, 99) for r in roles_permitidos]
    nivel_minimo_requerido = min(roles_validos) if roles_validos else 99
    
    return nivel_actual >= nivel_minimo_requerido

def obtener_modulos_permitidos(rol: str) -> list:
    """Retorna la lista de módulos visibles según el grupo de acceso."""
    rol_seguro = str(rol or "").strip()

    # ACCESO TOTAL: Admin y Coordinador / Administrativo
    if rol_seguro in ["Admin", "Coordinador / Administrativo"]:
        return [
            "Visitas y Agenda", "Clinica", "Pediatria", "Evolucion", "Estudios",
            "Materiales", "Recetas", "Balance", "Emergencias y Ambulancia",
            "Escalas Clinicas", "Historial", "PDF", "Telemedicina",
            "Dashboard", "Admision", "Inventario", "Caja", "Red de Profesionales",
            "Cierre Diario", "Mi Equipo", "Asistencia en Vivo", "RRHH y Fichajes",
            "Auditoria", "Auditoria Legal"
        ]
        
    # ACCESO LIMITADO: Operativo (Atención del paciente)
    if rol_seguro == "Operativo":
        return [
            "Visitas y Agenda", "Clinica", "Pediatria", "Evolucion", "Estudios",
            "Materiales", "Recetas", "Balance", "Emergencias y Ambulancia",
            "Escalas Clinicas", "Historial", "PDF", "Telemedicina"
        ]
    return []

def puede_accion(rol_actual, accion, roles_extra=None):
    roles_base = list(ACTION_ROLE_RULES.get(accion, []))
    if roles_extra:
        roles_base.extend(roles_extra)
    return tiene_permiso(rol_actual, roles_base)

def descripcion_acceso_rol(rol_actual):
    descripciones = {
        "Admin": "Control total del sistema, bases de datos y usuarios.",
        "Coordinador / Administrativo": "Acceso completo a gestión operativa, contable y clínica.",
        "Operativo": "Acceso restringido a la atención directa y registro del paciente.",
    }
    return descripciones.get(rol_actual, "Rol no configurado.")

def es_control_total(rol_actual):
    return rol_actual in {"Admin", "Coordinador / Administrativo"}

# --- UTILIDADES DE ARCHIVOS Y ASSETS (RESTAURADO) ---

@st.cache_data(show_spinner=False)
def cargar_texto_asset(nombre_archivo):
    """Carga archivos de texto (como CSS) desde la carpeta assets."""
    ruta = ASSETS_DIR / nombre_archivo
    if ruta.exists():
        return ruta.read_text(encoding="utf-8")
    return ""

@st.cache_data(show_spinner=False)
def cargar_json_asset(nombre_archivo):
    ruta = ASSETS_DIR / nombre_archivo
    if ruta.exists():
        with ruta.open("r", encoding="utf-8") as archivo:
            return json.load(archivo)
    return {}

# --- MANEJO DE DATOS Y PACIENTES ---

def filtrar_registros_empresa(items, mi_empresa, rol_actual, empresa_key="empresa"):
    if es_control_total(rol_actual):
        return list(items or [])
    empresa_actual = str(mi_empresa or "").strip().lower()
    return [i for i in (items or []) if str(i.get(empresa_key, "")).strip().lower() == empresa_actual]

def compactar_etiqueta_paciente(nombre, estado):
    nombre = str(nombre or "").strip()
    sufijo = " [ALTA]" if estado == "De Alta" else ""
    limite = 34 if sufijo else 40
    if len(nombre) > limite:
        nombre = f"{nombre[:limite - 3].rstrip()}..."
    return f"{nombre}{sufijo}"

def obtener_pacientes_visibles(session_state, mi_empresa, rol_actual, incluir_altas=False, busqueda=""):
    busqueda_norm = str(busqueda or "").strip().lower()
    detalles_db = session_state.get("detalles_pacientes_db", {})
    pacientes_visibles = []
    for paciente in session_state.get("pacientes_db", []):
        detalles = detalles_db.get(paciente, {})
        if not es_control_total(rol_actual):
            if str(detalles.get("empresa", "")).strip().lower() != str(mi_empresa or "").strip().lower():
                continue
        estado = detalles.get("estado", "Activo")
        if estado != "Activo" and not incluir_altas:
            continue
        dni = str(detalles.get("dni", ""))
        os = str(detalles.get("obra_social", ""))
        emp = str(detalles.get("empresa", ""))
        etiqueta = compactar_etiqueta_paciente(paciente, estado)
        if busqueda_norm and busqueda_norm not in f"{paciente} {dni} {os} {emp}".lower():
            continue
        pacientes_visibles.append((paciente, etiqueta, dni, os, estado, emp))
    pacientes_visibles.sort(key=lambda x: x[1].lower())
    return pacientes_visibles

# --- AUDITORÍA Y TIEMPO ---

def ahora():
    return datetime.now(ARG_TZ)

def registrar_auditoria_legal(tipo_evento, paciente, accion, actor, matricula="", detalle="", referencia="", extra=None, empresa=None):
    extra = extra or {}
    if empresa is None:
        detalles = st.session_state.get("detalles_pacientes_db", {}).get(paciente, {})
        empresa = detalles.get("empresa") or st.session_state.get("u_actual", {}).get("empresa", "")
    st.session_state.setdefault("auditoria_legal_db", [])
    st.session_state["auditoria_legal_db"].append({
        "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
        "tipo_evento": tipo_evento, "paciente": paciente, "accion": accion,
        "actor": actor, "matricula": matricula, "detalle": detalle,
        "referencia": referencia, "empresa": empresa, **extra
    })

# --- ESTADO INICIAL ---

def asegurar_usuarios_base():
    st.session_state.setdefault("usuarios_db", {})
    if "admin" not in st.session_state["usuarios_db"]:
        st.session_state["usuarios_db"]["admin"] = DEFAULT_ADMIN_USER.copy()

def inicializar_db_state(db):
    if "db_inicializada" not in st.session_state:
        claves = [
            "usuarios_db", "pacientes_db", "detalles_pacientes_db", "vitales_db", 
            "indicaciones_db", "evoluciones_db", "auditoria_legal_db", "consumos_db",
            "emergencias_db", "estudios_db", "balance_db", "pediatria_db", "fotos_heridas_db"
        ]
        for c in claves: 
            if c == "usuarios_db" or c == "detalles_pacientes_db":
                st.session_state.setdefault(c, {})
            else:
                st.session_state.setdefault(c, [])
        if db:
            for k, v in db.items(): st.session_state[k] = v
        asegurar_usuarios_base()
        st.session_state["db_inicializada"] = True

# --- OTROS ---

def obtener_alertas_clinicas(session_state, paciente_sel):
    if not paciente_sel: return []
    det = session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
    alertas = []
    if alg := str(det.get("alergias", "")).strip():
        alertas.append({"nivel": "critica", "titulo": "Alergias", "detalle": alg})
    if pat := str(det.get("patologias", "")).strip():
        alertas.append({"nivel": "media", "titulo": "Patologías", "detalle": pat})
    return alertas[:5]

def seleccionar_limite_registros(label, total, key, default=30, opciones=(10, 20, 30, 50, 100)):
    if total <= 0: return 0
    ops = sorted({v for v in opciones if v < total} | {total, min(total, default)})
    return st.selectbox(label, ops, index=ops.index(min(total, default)), key=key)

def optimizar_imagen_bytes(image_bytes, max_size=(1280, 1280), quality=75):
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            if img.mode not in ("RGB", "L"): img = img.convert("RGB")
            img.thumbnail(max_size)
            salida = BytesIO()
            img.save(salida, format="JPEG", optimize=True, quality=quality)
            return salida.getvalue(), "jpg"
    except: return image_bytes, None

def obtener_config_firma(key_prefix, default_liviano=True):
    if st.checkbox("Modo firma liviana", value=default_liviano, key=f"{key_prefix}_firma_liviana"):
        return {"height": 96, "width": 280, "stroke_width": 1.8, "display_toolbar": False}
    return {"height": 140, "width": 420, "stroke_width": 2.5, "display_toolbar": True}

def firma_a_base64(canvas_image_data=None, uploaded_file=None):
    try:
        if uploaded_file:
            f, _ = optimizar_imagen_bytes(uploaded_file.getvalue(), max_size=(700, 220), quality=55)
            return base64.b64encode(f).decode("utf-8")
        if canvas_image_data is not None:
            img = Image.fromarray(canvas_image_data.astype("uint8"), "RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            buf = BytesIO()
            bg.save(buf, format="JPEG", quality=55)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
    except: return ""
    return ""

def mostrar_dataframe_con_scroll(df, height=420, border=True, hide_index=True):
    with st.container(height=height, border=border):
        st.dataframe(df, use_container_width=True, hide_index=hide_index, height=height - 24)
