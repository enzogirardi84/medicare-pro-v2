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
    st.error(f"Error de dependencias: {e}")
    st.stop()

# --- UTILIDADES ---
cargar_texto_asset = getattr(core_utils, "cargar_texto_asset", lambda x: "")
es_control_total = core_utils.es_control_total
inicializar_db_state = core_utils.inicializar_db_state
obtener_modulos_permitidos = core_utils.obtener_modulos_permitidos
obtener_pacientes_visibles = core_utils.obtener_pacientes_visibles
obtener_alertas_clinicas = core_utils.obtener_alertas_clinicas
descripcion_acceso_rol = core_utils.descripcion_acceso_rol

# --- CONFIGURACIÓN UI ---
st.set_page_config(page_title="MediCare Enterprise PRO V9.12", layout="wide", initial_sidebar_state="collapsed")

if "_db_bootstrapped" not in st.session_state:
    inicializar_db_state(cargar_datos() if cargar_datos else None)
    st.session_state["_db_bootstrapped"] = True

# --- DICCIONARIOS DE NAVEGACIÓN ---
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
    elif tab_name == "Mi Equipo": render_fn(mi_empresa, rol, user)
    elif tab_name in ["Clinica", "Telemedicina", "Historial"]: render_fn(paciente_sel)
    else: render_fn(paciente_sel, user)

# =====================================================================
# BLOQUE DE PUBLICIDAD (LANDING PAGE) - RESTAURADO Y CORREGIDO
# =====================================================================
if not st.session_state.get("entered_app", False):
    st.markdown("""
        <style>
            /* Reset y fondo global */
            .stApp { background-color: #020617 !important; }
            #MainMenu, header, footer { visibility: hidden; }

            .landing-container {
                font-family: 'Inter', sans-serif;
                color: #f8fafc;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 60px 20px;
                max-width: 1200px;
                margin: 0 auto;
            }

            .main-title {
                font-size: 4rem;
                font-weight: 900;
                text-align: center;
                background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 10px;
            }

            .main-subtitle {
                font-size: 1.4rem;
                color: #94a3b8;
                text-align: center;
                margin-bottom: 50px;
                max-width: 800px;
            }

            /* Grilla de tarjetas con efecto cristal */
            .grid-cards {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
                gap: 25px;
                width: 100%;
                margin-bottom: 60px;
            }

            .glass-card {
                background: rgba(30, 41, 59, 0.4);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 24px;
                padding: 35px;
                transition: transform 0.3s ease, border-color 0.3s ease;
            }

            .glass-card:hover {
                transform: translateY(-8px);
                border-color: #38bdf8;
                background: rgba(30, 41, 59, 0.6);
            }

            .card-icon { font-size: 2.5rem; margin-bottom: 15px; }
            .card-title { font-size: 1.3rem; font-weight: 700; color: #fff; margin-bottom: 10px; }
            .card-text { color: #cbd5e1; font-size: 0.95rem; line-height: 1.6; }

            /* Caja de contacto */
            .contact-box {
                background: linear-gradient(145deg, #0f172a, #1e293b);
                border: 1px solid #38bdf8;
                border-radius: 32px;
                padding: 45px;
                text-align: center;
                width: 100%;
                box-shadow: 0 20px 40px rgba(0,0,0,0.3);
            }
            
            .dev-card {
                background: rgba(255,255,255,0.03);
                padding: 20px;
                border-radius: 20px;
                min-width: 280px;
                border: 1px solid rgba(255,255,255,0.05);
            }
        </style>

        <div class="landing-container">
            <h1 class="main-title">MediCare Enterprise PRO</h1>
            <p class="main-subtitle">Potenciando la gestión de salud con trazabilidad total, seguridad legal y eficiencia clínica de alto rendimiento.</p>
            
            <div class="grid-cards">
                <div class="glass-card">
                    <div class="card-icon">📍</div>
                    <div class="card-title">Trazabilidad GPS</div>
                    <div class="card-text">Control exacto de asistencia en domicilio verificado por geolocalización.</div>
                </div>
                <div class="glass-card">
                    <div class="card-icon">🩺</div>
                    <div class="card-title">Historia Clínica</div>
                    <div class="card-text">Evoluciones multidisciplinarias y signos vitales en tiempo real.</div>
                </div>
                <div class="glass-card">
                    <div class="card-icon">💊</div>
                    <div class="card-title">Gestión de Insumos</div>
                    <div class="card-text">Descuento automático de stock integrado al registro de prácticas.</div>
                </div>
                <div class="glass-card">
                    <div class="card-icon">⚖️</div>
                    <div class="card-title">Auditoría Legal</div>
                    <div class="card-text">Cada acción queda firmada y auditada para máxima protección institucional.</div>
                </div>
            </div>

            <div class="contact-box">
                <h2 style="color:white; margin-bottom:10px;">¿Soporte o Implementación?</h2>
                <p style="color:#94a3b8; margin-bottom:30px;">Hable directamente con los creadores de la plataforma.</p>
                <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 25px;">
                    <div class="dev-card">
                        <h4 style="color:#38bdf8; margin:0;">Enzo N. Girardi</h4>
                        <p style="font-size:0.85rem; color:#64748b; margin-bottom:12px;">Arquitectura y Soporte</p>
                        <a href="https://wa.me/5493584302024" style="color:white; text-decoration:none; font-weight:700; background:#22c55e; padding:8px 16px; border-radius:12px;">WhatsApp 📲</a>
                    </div>
                    <div class="dev-card">
                        <h4 style="color:#38bdf8; margin:0;">Dario Lanfranco</h4>
                        <p style="font-size:0.85rem; color:#64748b; margin-bottom:12px;">Implementación</p>
                        <a href="https://wa.me/5493584201263" style="color:white; text-decoration:none; font-weight:700; background:#22c55e; padding:8px 16px; border-radius:12px;">WhatsApp 📲</a>
                    </div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 INGRESAR AL SISTEMA", key="btn_ingresar_main", use_container_width=True):
        st.session_state.entered_app = True
        st.rerun()
    st.stop()

# --- LOGIN Y CONTROL DE ACCESO ---
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
    buscar = st.text_input("Buscador rápido", placeholder="Nombre o DNI...")
    ver_altas = st.checkbox("Incluir Altas") if es_control_total(rol) else False
    
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

# --- NAVEGACIÓN CENTRAL ---
if not menu:
    st.error("No tienes módulos asignados.")
else:
    vista_actual = st.session_state.get("modulo_actual", menu[0])
    if vista_actual not in menu: vista_actual = menu[0]
    
    selected = st.pills("Menú de Módulos", menu, default=vista_actual, format_func=lambda x: VIEW_NAV_LABELS.get(x, x), key="main_nav_pills")
    
    if selected:
        st.session_state["modulo_actual"] = selected
        vista_actual = selected
    
    if paciente_sel:
        det = st.session_state["detalles_pacientes_db"].get(paciente_sel, {})
        st.info(f"**Paciente:** {paciente_sel} | **DNI:** {det.get('dni','S/D')}")

    render_current_view(vista_actual, paciente_sel, mi_empresa, user, rol)
