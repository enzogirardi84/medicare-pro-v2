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
# LANDING PAGE (PUBLICIDAD ULTRA-PREMIUM V3.2 - 100% FUNCIONAL)
# =====================================================================
if not st.session_state.get("entered_app", False):
    
    html_publicidad = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
        
        .stApp { background-image: radial-gradient(circle at top right, #1e293b 0%, #020617 100%) !important; }
        #MainMenu, header, footer, .st-emotion-cache-1r4qj8v { visibility: hidden !important; }
        
        .landing-container {
            font-family: 'Inter', sans-serif;
            color: #f8fafc;
            max-width: 1280px;
            margin: 0 auto;
            padding: 40px 20px 100px;
            text-align: center;
        }
        
        .badge-new {
            background: linear-gradient(90deg, #38bdf8, #818cf8);
            color: #020617;
            padding: 8px 20px;
            border-radius: 50px;
            font-size: 0.85rem;
            font-weight: 900;
            display: inline-block;
            margin-bottom: 20px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .main-title {
            font-size: clamp(2.8rem, 7vw, 5.2rem);
            font-weight: 900;
            background: linear-gradient(135deg, #ffffff 30%, #38bdf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            line-height: 1.05;
            margin-bottom: 24px;
        }
        
        .subtitle {
            color: #94a3b8;
            font-size: 1.25rem;
            max-width: 820px;
            margin: 0 auto 50px;
        }
        
        .stats-container {
            display: flex;
            gap: 40px;
            justify-content: center;
            flex-wrap: wrap;
            margin-bottom: 60px;
        }
        
        .stat-item { text-align: center; min-width: 110px; }
        .stat-num {
            font-size: 2.6rem;
            font-weight: 900;
            color: #38bdf8;
            display: block;
            line-height: 1;
        }
        .stat-label {
            font-size: 0.85rem;
            color: #64748b;
            text-transform: uppercase;
            font-weight: 600;
        }
        
        .grid-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 24px;
            max-width: 1200px;
            margin: 0 auto 70px;
        }
        
        .glass-card {
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 28px;
            padding: 38px 32px;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            text-align: left;
        }
        
        .glass-card:hover {
            transform: translateY(-12px);
            border-color: #38bdf8;
            background: rgba(56, 189, 248, 0.08);
            box-shadow: 0 20px 40px rgba(56, 189, 248, 0.15);
        }
        
        .card-icon { font-size: 3rem; margin-bottom: 20px; display: block; }
        .card-title { 
            font-size: 1.35rem; 
            font-weight: 700; 
            color: #fff; 
            margin-bottom: 12px;
        }
        .card-text {
            color: #cbd5e1;
            line-height: 1.65;
            font-size: 0.96rem;
        }
        
        .modules-section {
            background: rgba(255,255,255,0.03);
            border-radius: 28px;
            padding: 40px 30px;
            margin-bottom: 70px;
            border: 1px solid rgba(255,255,255,0.08);
        }
        
        .module-tag {
            display: inline-block;
            background: rgba(56, 189, 248, 0.12);
            color: #38bdf8;
            padding: 8px 18px;
            border-radius: 9999px;
            margin: 6px;
            font-size: 0.9rem;
            font-weight: 600;
            border: 1px solid rgba(56, 189, 248, 0.2);
        }
        
        .contact-section {
            background: #0f172a;
            border-radius: 32px;
            padding: 50px 40px;
            border: 1px solid rgba(56, 189, 248, 0.25);
        }
        
        .dev-card {
            background: rgba(0,0,0,0.25);
            padding: 28px;
            border-radius: 20px;
            border: 1px solid rgba(255,255,255,0.08);
        }
        
        .stButton > button {
            background: linear-gradient(90deg, #38bdf8, #818cf8) !important;
            color: white !important;
            font-size: 1.35rem !important;
            font-weight: 700 !important;
            padding: 18px 50px !important;
            border-radius: 50px !important;
            box-shadow: 0 10px 30px rgba(56, 189, 248, 0.4) !important;
            transition: all 0.3s ease !important;
        }
        .stButton > button:hover {
            transform: scale(1.05);
            box-shadow: 0 15px 40px rgba(56, 189, 248, 0.5) !important;
        }
    </style>

    <div class="landing-container">
        <div class="badge-new">Versión 9.12 Enterprise PRO</div>
        <h1 class="main-title">Escale su Operación<br>Médica al Siguiente Nivel</h1>
        <p class="subtitle">
            La plataforma líder en gestión clínica y operativa.<br>
            Control total sobre equipos, insumos y trazabilidad legal de pacientes.
        </p>

        <div class="stats-container">
            <div class="stat-item"><span class="stat-num">100%</span><span class="stat-label">Digital</span></div>
            <div class="stat-item"><span class="stat-num">+50</span><span class="stat-label">Módulos</span></div>
            <div class="stat-item"><span class="stat-num">GPS</span><span class="stat-label">Real Time</span></div>
        </div>

        <div class="grid-cards">
            <div class="glass-card">
                <span class="card-icon">🛰️</span>
                <h3 class="card-title">Geolocalización</h3>
                <p class="card-text">Auditoría satelital de visitas. Sepa exactamente dónde y cuándo se realizó la atención.</p>
            </div>
            <div class="glass-card">
                <span class="card-icon">📂</span>
                <h3 class="card-title">Historia Clínica</h3>
                <p class="card-text">Evoluciones multidisciplinarias con adjunto de fotos de heridas y estudios en tiempo real.</p>
            </div>
            <div class="glass-card">
                <span class="card-icon">💳</span>
                <h3 class="card-title">Finanzas & Honorarios</h3>
                <p class="card-text">Liquidación automatizada de profesionales y control estricto de ingresos y egresos.</p>
            </div>
            <div class="glass-card">
                <span class="card-icon">🛡️</span>
                <h3 class="card-title">Blindaje Legal</h3>
                <p class="card-text">Recetas y consentimientos con firma digital biométrica y validez jurídica total.</p>
            </div>
        </div>

        <div class="modules-section">
            <h3 style="margin-bottom:25px; color:white; font-size:1.4rem;">Ecosistema Integrado</h3>
            <div class="module-tag">Pediatría</div>
            <div class="module-tag">Telemedicina</div>
            <div class="module-tag">Gestión Stock</div>
            <div class="module-tag">Auditoría</div>
            <div class="module-tag">RRHH</div>
            <div class="module-tag">Balances</div>
            <div class="module-tag">Red de Profesionales</div>
        </div>

        <div class="contact-section">
            <h2 style="color:white; margin-bottom:35px;">Soporte e Implementación</h2>
            <div style="display: flex; flex-wrap: wrap; gap: 25px; justify-content: center;">
                <div class="dev-card">
                    <div style="color:#38bdf8; font-weight:800; font-size:0.85rem;">TECNOLOGÍA</div>
                    <div style="font-size:1.55rem; font-weight:900;">Enzo N. Girardi</div>
                    <a href="https://wa.me/5493584302024" target="_blank" style="display:block; background:#22c55e; color:white; padding:14px; border-radius:15px; text-decoration:none; font-weight:700; margin-top:15px; text-align:center;">SOPORTE TÉCNICO 📲</a>
                </div>
                <div class="dev-card">
                    <div style="color:#38bdf8; font-weight:800; font-size:0.85rem;">NEGOCIOS</div>
                    <div style="font-size:1.55rem; font-weight:900;">Dario Lanfranco</div>
                    <a href="https://wa.me/5493584201263" target="_blank" style="display:block; background:#22c55e; color:white; padding:14px; border-radius:15px; text-decoration:none; font-weight:700; margin-top:15px; text-align:center;">CONTRATACIONES 📲</a>
                </div>
            </div>
        </div>
    </div>
    """

    st.markdown(html_publicidad, unsafe_allow_html=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🚀 INGRESAR AL SISTEMA", key="btn_ingresar_main", use_container_width=True):
        st.session_state.entered_app = True
        st.rerun()
    
    st.stop()
