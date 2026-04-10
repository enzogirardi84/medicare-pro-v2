import base64
import json
import sys
from html import escape
from importlib import import_module
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from core.auth import check_inactividad, render_login
    from core import utils as core_utils
    from core.database import cargar_datos
except ImportError:
    core_auth = import_module("core.auth")
    check_inactividad, render_login = core_auth.check_inactividad, core_auth.render_login
    core_utils = import_module("core.utils")
    cargar_datos = import_module("core.database").cargar_datos

# --- Utilidades ---
cargar_texto_asset = core_utils.cargar_texto_asset
es_control_total = core_utils.es_control_total
inicializar_db_state = core_utils.inicializar_db_state
obtener_modulos_permitidos = core_utils.obtener_modulos_permitidos
obtener_pacientes_visibles = core_utils.obtener_pacientes_visibles
obtener_alertas_clinicas = core_utils.obtener_alertas_clinicas

# --- Configuración UI ---
st.set_page_config(page_title="MediCare Enterprise PRO V9.12", layout="wide", initial_sidebar_state="collapsed")

if "_db_bootstrapped" not in st.session_state:
    inicializar_db_state(cargar_datos() if cargar_datos else None)
    st.session_state["_db_bootstrapped"] = True

VIEW_CONFIG = {
    "Visitas y Agenda": ("views.visitas", "render_visitas"), "Dashboard": ("views.dashboard", "render_dashboard"),
    "Admision": ("views.admision", "render_admision"), "Clinica": ("views.clinica", "render_clinica"),
    "Pediatria": ("views.pediatria", "render_pediatria"), "Evolucion": ("views.evolucion", "render_evolucion"),
    "Estudios": ("views.estudios", "render_estudios"), "Materiales": ("views.materiales", "render_materiales"),
    "Recetas": ("views.recetas", "render_recetas"), "Balance": ("views.balance", "render_balance"),
    "Inventario": ("views.inventario", "render_inventario"), "Caja": ("views.caja", "render_caja"),
    "Emergencias y Ambulancia": ("views.emergencias", "render_emergencias"), "Red de Profesionales": ("views.red_profesionales", "render_red_profesionales"),
    "Escalas Clinicas": ("views.escalas_clinicas", "render_escalas_clinicas"), "Historial": ("views.historial", "render_historial"),
    "PDF": ("views.pdf_view", "render_pdf"), "Telemedicina": ("views.telemedicina", "render_telemedicina"),
    "Cierre Diario": ("views.cierre_diario", "render_cierre_diario"), "Mi Equipo": ("views.mi_equipo", "render_mi_equipo"),
    "Asistencia en Vivo": ("views.asistencia", "render_asistencia"), "RRHH y Fichajes": ("views.rrhh", "render_rrhh"),
    "Auditoria": ("views.auditoria", "render_auditoria"), "Auditoria Legal": ("views.auditoria_legal", "render_auditoria_legal"),
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
    module_name, function_name = VIEW_CONFIG[tab_name]
    render_fn = getattr(import_module(module_name), function_name)
    if tab_name in ["Visitas y Agenda", "Recetas", "Caja", "PDF"]: render_fn(paciente_sel, mi_empresa, user, rol)
    elif tab_name in ["Admision", "Dashboard", "Inventario"]: render_fn(mi_empresa, rol)
    elif tab_name in ["Evolucion", "Estudios", "Red de Profesionales", "RRHH y Fichajes"]: render_fn(paciente_sel, user, rol)
    elif tab_name in ["Mi Equipo"]: render_fn(mi_empresa, rol, user)
    elif tab_name in ["Clinica", "Telemedicina", "Historial"]: render_fn(paciente_sel)
    else: render_fn(paciente_sel, user)

# --- Landing de Publicidad ---
if not st.session_state.get("entered_app", False):
    st.markdown("<h1 style='text-align:center; color:white;'>MediCare Enterprise PRO</h1>", unsafe_allow_html=True)
    if st.button("🚀 INGRESAR AL SISTEMA", key="btn_ingresar_main"):
        st.session_state.entered_app = True
        st.rerun()
    st.stop()

render_login()
check_inactividad()

user = st.session_state.get("u_actual")
if not user: st.stop()

mi_empresa, rol = user["empresa"], user["rol"]

with st.sidebar:
    st.markdown(f"### {mi_empresa}\n**{user['nombre']}** ({rol})")
    st.divider()
    
    # MOTOR DE PERMISOS
    menu = obtener_modulos_permitidos(rol)
    
    st.markdown("### Pacientes")
    buscar = st.text_input("Buscar Paciente")
    ver_altas = st.checkbox("Mostrar Altas") if es_control_total(rol) else False
    p_f = obtener_pacientes_visibles(st.session_state, mi_empresa, rol, incluir_altas=ver_altas, busqueda=buscar)
    
    paciente_sel = None
    if p_f:
        paciente_actual = st.session_state.get("paciente_actual")
        idx = [i[0] for i in p_f].index(paciente_actual) if paciente_actual in [i[0] for i in p_f] else 0
        paciente_sel_tuple = st.selectbox("Seleccionar Paciente", p_f, index=idx, format_func=lambda x: x[1])
        paciente_sel = paciente_sel_tuple[0]
        st.session_state["paciente_actual"] = paciente_sel
        
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# Navegación Central
if not menu:
    st.error("No tienes módulos asignados.")
else:
    vista_actual = st.session_state.get("modulo_actual", menu[0])
    if vista_actual not in menu: vista_actual = menu[0]
    
    selected = st.pills("Módulos", menu, default=vista_actual, format_func=lambda x: VIEW_NAV_LABELS.get(x, x))
    if selected: st.session_state["modulo_actual"] = selected
    
    render_current_view(st.session_state["modulo_actual"], paciente_sel, mi_empresa, user, rol)
