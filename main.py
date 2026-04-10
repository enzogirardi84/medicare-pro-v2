import base64
import json
import sys
from html import escape
from importlib import import_module
from pathlib import Path

import streamlit as st

# Configuración de rutas para importaciones locales
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# --- IMPORTACIONES DINÁMICAS ---
try:
    from core.auth import check_inactividad, render_login
    from core import utils as core_utils
    from core.database import cargar_datos
except ImportError as e:
    st.error(f"Error crítico de dependencias: {e}")
    st.stop()

# --- ASIGNACIÓN DE UTILIDADES ---
# Usamos getattr para evitar el AttributeError si alguna función falta en utils.py
cargar_texto_asset = getattr(core_utils, "cargar_texto_asset", lambda x: "")
es_control_total = getattr(core_utils, "es_control_total", lambda r: r in ["Admin", "Coordinador / Administrativo"])
inicializar_db_state = core_utils.inicializar_db_state
obtener_modulos_permitidos = core_utils.obtener_modulos_permitidos
obtener_pacientes_visibles = core_utils.obtener_pacientes_visibles
obtener_alertas_clinicas = core_utils.obtener_alertas_clinicas
descripcion_acceso_rol = core_utils.descripcion_acceso_rol
tiene_permiso = core_utils.tiene_permiso

# --- CONFIGURACIÓN UI ---
st.set_page_config(page_title="MediCare Enterprise PRO V9.12", layout="wide", initial_sidebar_state="collapsed")

# Inyección de CSS Global
css_content = cargar_texto_asset('style.css')
if css_content:
    st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)

# Bootstrapping de la Base de Datos
if "_db_bootstrapped" not in st.session_state:
    try:
        data_inicial = cargar_datos()
        inicializar_db_state(data_inicial)
    except Exception:
        inicializar_db_state(None)
    st.session_state["_db_bootstrapped"] = True

# --- CONFIGURACIÓN DE MÓDULOS ---
VIEW_CONFIG = {
    "Visitas y Agenda": ("views.visitas", "render_visitas"), 
    "Dashboard": ("views.dashboard", "render_dashboard"),
    "Admision": ("views.admision", "render_admision"), 
    "Clinica": ("views.clinica", "render_clinica"),
    "Pediatria": ("views.pediatria", "render_pediatria"), 
    "Evolucion": ("views.evolucion", "render_evolucion"),
    "Estudios": ("views.estudios", "render_estudios"), 
    "Materiales": ("views.materiales", "render_materiales"),
    "Recetas": ("views.recetas", "render_recetas"), 
    "Balance": ("views.balance", "render_balance"),
    "Inventario": ("views.inventario", "render_inventario"), 
    "Caja": ("views.caja", "render_caja"),
    "Emergencias y Ambulancia": ("views.emergencias", "render_emergencias"), 
    "Red de Profesionales": ("views.red_profesionales", "render_red_profesionales"),
    "Escalas Clinicas": ("views.escalas_clinicas", "render_escalas_clinicas"), 
    "Historial": ("views.historial", "render_historial"),
    "PDF": ("views.pdf_view", "render_pdf"), 
    "Telemedicina": ("views.telemedicina", "render_telemedicina"),
    "Cierre Diario": ("views.cierre_diario", "render_cierre_diario"), 
    "Mi Equipo": ("views.mi_equipo", "render_mi_equipo"),
    "Asistencia en Vivo": ("views.asistencia", "render_asistencia"), 
    "RRHH y Fichajes": ("views.rrhh", "render_rrhh"),
    "Auditoria": ("views.auditoria", "render_auditoria"), 
    "Auditoria Legal": ("views.auditoria_legal", "render_auditoria_legal"),
}

VIEW_NAV_LABELS = {
    "Visitas y Agenda": "📍 Visitas", "Dashboard": "📊 Dashboard", "Admision": "🧾 Admisión",
    "Clinica": "🩺 Clínica", "Pediatria": "👶 Pediatría", "Evolucion": "✍️ Evolución",
    "Estudios": "🧪 Estudios", "Materiales": "📦 Materiales", "Recetas": "💊 Recetas",
    "Balance": "💧 Balance", "Inventario": "🏥 Inventario", "Caja": "💵 Caja",
    "Emergencias y Ambulancia": "🚑 Emergencias", "Red de Profesionales": "🤝 Red",
    "Escalas Clinicas": "📏 Escalas", "Historial": "🗂️ Historial", "PDF": "📄 PDF",
    "Telemedicina": "🎥 Telemedicina", "Cierre Diario": "🧮 Cierre", "Mi Equipo": "👥 Equipo",
    "Asistencia en Vivo": "🛰️ Asistencia", "RRHH y Fichajes": "⏱️ RRHH", "Auditoria": "🔎 Auditoría",
    "Auditoria Legal": "⚖️ Legal",
}

def render_current_view(tab_name, paciente_sel, mi_empresa, user, rol):
    """Enrutador de renderizado con inyección de dependencias."""
    if tab_name not in VIEW_CONFIG: return
    module_name, function_name = VIEW_CONFIG[tab_name]
    render_fn = getattr(import_module(module_name), function_name)
    
    if tab_name in ["Visitas y Agenda", "Recetas", "Caja", "PDF"]:
        render_fn(paciente_sel, mi_empresa, user, rol)
    elif tab_name in ["Admision", "Dashboard", "Inventario"]:
        render_fn(mi_empresa, rol)
    elif tab_name in ["Evolucion", "Estudios", "Red de Profesionales", "RRHH y Fichajes"]:
        render_fn(paciente_sel, user, rol)
    elif tab_name == "Mi Equipo":
        render_fn(mi_empresa, rol, user)
    elif tab_name in ["Clinica", "Telemedicina", "Historial"]:
        render_fn(paciente_sel)
    else:
        render_fn(paciente_sel, user)

# --- LANDING PAGE (PUBLICIDAD) ---
if not st.session_state.get("entered_app", False):
    st.markdown(
        """
        <div style='text-align:center; padding: 100px 20px;'>
            <h1 style='font-size: 4rem; font-weight: 900; background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
                MediCare Enterprise PRO
            </h1>
            <p style='color: #cbd5e1; font-size: 1.5rem; margin-bottom: 40px;'>
                Gestión clínica, operativa y legal en una sola plataforma integrada.
            </p>
        </div>
        """, unsafe_allow_html=True
    )
    if st.button("🚀 INGRESAR AL SISTEMA", key="btn_ingresar_main", use_container_width=True):
        st.session_state.entered_app = True
        st.rerun()
    st.stop()

# --- CONTROL DE ACCESO ---
render_login()
check_inactividad()

user = st.session_state.get("u_actual")
if not user: st.stop()

mi_empresa, rol = user["empresa"], user["rol"]

# --- SIDEBAR (GESTIÓN DE PACIENTES) ---
with st.sidebar:
    st.markdown(f"### {mi_empresa}\n**{user['nombre']}** ({rol})")
    st.caption(descripcion_acceso_rol(rol))
    st.divider()
    
    # Motor de Permisos (Obtiene los módulos según los 3 niveles de acceso)
    menu = obtener_modulos_permitidos(rol)
    
    st.markdown("### 👤 Pacientes")
    buscar = st.text_input("Buscador rápido", placeholder="Nombre o DNI...")
    ver_altas = st.checkbox("Incluir Pacientes de Alta") if es_control_total(rol) else False
    
    p_f = obtener_pacientes_visibles(st.session_state, mi_empresa, rol, incluir_altas=ver_altas, busqueda=buscar)
    
    paciente_sel = None
    if p_f:
        paciente_actual = st.session_state.get("paciente_actual")
        opciones_ids = [i[0] for i in p_f]
        idx = opciones_ids.index(paciente_actual) if paciente_actual in opciones_ids else 0
        paciente_sel_tuple = st.selectbox("Seleccionar para atención", p_f, index=idx, format_func=lambda x: x[1])
        paciente_sel = paciente_sel_tuple[0]
        st.session_state["paciente_actual"] = paciente_sel
    
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# --- NAVEGACIÓN Y RENDERIZADO CENTRAL ---
if not menu:
    st.error("No tienes módulos asignados. Contacta al administrador.")
else:
    vista_actual = st.session_state.get("modulo_actual", menu[0])
    if vista_actual not in menu: vista_actual = menu[0]
    
    # Selector de módulos estilo Pills
    selected = st.pills(
        "Módulos del Sistema", 
        menu, 
        default=vista_actual, 
        format_func=lambda x: VIEW_NAV_LABELS.get(x, x),
        key="main_nav_pills"
    )
    
    if selected:
        st.session_state["modulo_actual"] = selected
        vista_actual = selected
    
    # Header del paciente activo en el área central
    if paciente_sel:
        det = st.session_state["detalles_pacientes_db"].get(paciente_sel, {})
        st.info(f"**Atendiendo a:** {paciente_sel} | **DNI:** {det.get('dni','S/D')} | **O.S:** {det.get('obra_social','S/D')}")

    render_current_view(vista_actual, paciente_sel, mi_empresa, user, rol)
