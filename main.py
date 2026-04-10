import base64
import json
import sys
from html import escape
from importlib import import_module
from pathlib import Path
import streamlit as st

# Configuración de rutas
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# --- IMPORTACIONES ---
try:
    from core.auth import check_inactividad, render_login
    from core import utils as core_utils
    from core.database import cargar_datos
except ImportError as e:
    st.error(f"Error crítico de dependencias: {e}")
    st.stop()

# --- ASIGNACIÓN DE UTILIDADES ---
cargar_texto_asset = core_utils.cargar_texto_asset
es_control_total = core_utils.es_control_total
inicializar_db_state = core_utils.inicializar_db_state
obtener_modulos_permitidos = core_utils.obtener_modulos_permitidos
obtener_pacientes_visibles = core_utils.obtener_pacientes_visibles
obtener_alertas_clinicas = core_utils.obtener_alertas_clinicas
descripcion_acceso_rol = core_utils.descripcion_acceso_rol
tiene_permiso = core_utils.tiene_permiso

# --- CONFIGURACIÓN UI ---
st.set_page_config(page_title="MediCare Enterprise PRO V9.12", layout="wide", initial_sidebar_state="collapsed")

# Inyección de CSS
css_content = cargar_texto_asset('style.css')
if css_content:
    st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)

if "_db_bootstrapped" not in st.session_state:
    inicializar_db_state(cargar_datos() if cargar_datos else None)
    st.session_state["_db_bootstrapped"] = True

# --- DICCIONARIOS ---
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

VIEW_NAV_LABELS = { k: f"🔹 {k}" for k in VIEW_CONFIG.keys() }

def render_current_view(tab_name, paciente_sel, mi_empresa, user, rol):
    if tab_name not in VIEW_CONFIG: return
    module_name, function_name = VIEW_CONFIG[tab_name]
    render_fn = getattr(import_module(module_name), function_name)
    if tab_name in ["Visitas y Agenda", "Recetas", "Caja", "PDF"]: render_fn(paciente_sel, mi_empresa, user, rol)
    elif tab_name in ["Admision", "Dashboard", "Inventario"]: render_fn(mi_empresa, rol)
    elif tab_name in ["Evolucion", "Estudios", "Red de Profesionales", "RRHH y Fichajes"]: render_fn(paciente_sel, user, rol)
    elif tab_name == "Mi Equipo": render_fn(mi_empresa, rol, user)
    elif tab_name in ["Clinica", "Telemedicina", "Historial"]: render_fn(paciente_sel)
    else: render_fn(paciente_sel, user)

# =====================================================================
# LANDING PAGE (PUBLICIDAD)
# =====================================================================
if not st.session_state.get("entered_app", False):
    st.markdown("""
        <style>
            .stApp { background-image: radial-gradient(circle at top right, #1e293b 0%, #020617 80%) !important; }
            #MainMenu, header, footer { visibility: hidden; }
            .landing-container { font-family: 'Inter', sans-serif; color: #f8fafc; display: flex; flex-direction: column; align-items: center; padding: 40px 20px; }
            .main-title { font-size: 3.5rem; font-weight: 900; background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px; }
            .grid-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 20px; width: 100%; max-width: 1200px; margin-bottom: 50px; }
            .glass-card { background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 24px; padding: 30px; transition: 0.3s; }
            .glass-card:hover { transform: translateY(-5px); border-color: #38bdf8; background: rgba(255, 255, 255, 0.06); }
            .contact-box { background: rgba(15, 23, 42, 0.8); border: 1px solid #38bdf8; border-radius: 30px; padding: 40px; text-align: center; width: 100%; }
            .dev-card { background: rgba(255,255,255,0.03); padding: 15px; border-radius: 15px; min-width: 250px; border: 1px solid rgba(255,255,255,0.05); }
        </style>
        <div class="landing-container">
            <h1 class="main-title">MediCare Enterprise PRO</h1>
            <p style='color:#94a3b8; font-size:1.2rem; margin-bottom:40px;'>Gestión clínica, operativa y legal en una sola plataforma integrada.</p>
            <div class="grid-cards">
                <div class="glass-card"><div style='font-size:2.2rem;'>📍</div><div style='font-weight:700; color:#fff;'>Trazabilidad GPS</div><div style='color:#cbd5e1; font-size:0.9rem;'>Control de asistencia verificado por geolocalización.</div></div>
                <div class="glass-card"><div style='font-size:2.2rem;'>🩺</div><div style='font-weight:700; color:#fff;'>Historia Clínica</div><div style='color:#cbd5e1; font-size:0.9rem;'>Evoluciones y signos vitales en tiempo real.</div></div>
                <div class="glass-card"><div style='font-size:2.2rem;'>💊</div><div style='font-weight:700; color:#fff;'>Gestión de Insumos</div><div style='color:#cbd5e1; font-size:0.9rem;'>Descuento automático de stock integrado.</div></div>
                <div class="glass-card"><div style='font-size:2.2rem;'>⚖️</div><div style='font-weight:700; color:#fff;'>Auditoría Legal</div><div style='color:#cbd5e1; font-size:0.9rem;'>Cada acción queda firmada y auditada legalmente.</div></div>
            </div>
            <div class="contact-box">
                <h2 style="color:white; margin-bottom:10px;">¿Soporte o Implementación?</h2>
                <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 20px;">
                    <div class="dev-card"><h4 style="color:#38bdf8; margin:0;">Enzo N. Girardi</h4><a href="https://wa.me/5493584302024" style="color:#22c55e; text-decoration:none; font-weight:700;">WhatsApp 📲</a></div>
                    <div class="dev-card"><h4 style="color:#38bdf8; margin:0;">Dario Lanfranco</h4><a href="https://wa.me/5493584201263" style="color:#22c55e; text-decoration:none; font-weight:700;">WhatsApp 📲</a></div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    if st.button("🚀 INGRESAR AL SISTEMA", key="btn_ingresar_main", use_container_width=True):
        st.session_state.entered_app = True
        st.rerun()
    st.stop()

# --- LOGIN ---
render_login()
check_inactividad()
user = st.session_state.get("u_actual")
if not user: st.stop()
mi_empresa, rol = user["empresa"], user["rol"]

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### {mi_empresa}\n**{user['nombre']}** ({rol})")
    st.caption(descripcion_acceso_rol(rol))
    st.divider()
    menu = obtener_modulos_permitidos(rol)
    st.markdown("### 👤 Pacientes")
    buscar = st.text_input("Buscador...")
    p_f = obtener_pacientes_visibles(st.session_state, mi_empresa, rol, busqueda=buscar)
    paciente_sel = None
    if p_f:
        idx = 0
        p_sel_tuple = st.selectbox("Seleccionar para atención", p_f, index=idx, format_func=lambda x: x[1])
        paciente_sel = p_sel_tuple[0]
        st.session_state["paciente_actual"] = paciente_sel
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# --- NAVEGACIÓN ---
if menu:
    vista_actual = st.session_state.get("modulo_actual", menu[0])
    if vista_actual not in menu: vista_actual = menu[0]
    selected = st.pills("Menú", menu, default=vista_actual, format_func=lambda x: VIEW_NAV_LABELS.get(x, x))
    if selected:
        st.session_state["modulo_actual"] = selected
        vista_actual = selected
    if paciente_sel:
        st.info(f"**Paciente:** {paciente_sel}")
    render_current_view(vista_actual, paciente_sel, mi_empresa, user, rol)
