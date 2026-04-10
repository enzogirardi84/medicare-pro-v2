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
# LANDING PAGE (PUBLICIDAD ULTRA-PREMIUM V3.0)
# =====================================================================
if not st.session_state.get("entered_app", False):
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
            
            .stApp { 
                background-image: radial-gradient(circle at top right, #1e293b 0%, #020617 100%) !important; 
            }
            #MainMenu, header, footer { visibility: hidden; }

            .landing-container {
                font-family: 'Inter', sans-serif;
                color: #f8fafc;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 40px 20px;
                text-align: center;
            }

            .badge-new {
                background: linear-gradient(90deg, #38bdf8, #818cf8);
                color: #020617;
                padding: 5px 15px;
                border-radius: 50px;
                font-size: 0.8rem;
                font-weight: 800;
                margin-bottom: 20px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }

            .main-title {
                font-size: clamp(2.8rem, 7vw, 5.5rem);
                font-weight: 900;
                letter-spacing: -3px;
                background: linear-gradient(135deg, #fff 30%, #38bdf8;);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                line-height: 1;
                margin-bottom: 25px;
            }

            /* SECCIÓN DE STATS */
            .stats-container {
                display: flex;
                gap: 40px;
                margin-bottom: 60px;
                flex-wrap: wrap;
                justify-content: center;
            }
            .stat-item { text-align: center; }
            .stat-num { font-size: 2.5rem; font-weight: 900; color: #38bdf8; display: block; }
            .stat-label { font-size: 0.9rem; color: #64748b; text-transform: uppercase; }

            /* GRILLA PRINCIPAL */
            .grid-cards {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 25px;
                width: 100%;
                max-width: 1300px;
                margin-bottom: 80px;
            }

            .glass-card {
                background: rgba(255, 255, 255, 0.02);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 35px;
                padding: 40px;
                transition: all 0.4s cubic-bezier(0.23, 1, 0.32, 1);
                text-align: left;
                position: relative;
                overflow: hidden;
            }

            .glass-card:hover {
                transform: translateY(-15px);
                border-color: #38bdf8;
                background: rgba(56, 189, 248, 0.04);
            }

            .card-icon { font-size: 3rem; margin-bottom: 20px; display: block; }
            .card-title { font-size: 1.6rem; font-weight: 700; color: #fff; margin-bottom: 10px; }
            .card-text { color: #94a3b8; font-size: 1rem; line-height: 1.6; }

            /* SECCIÓN MODULOS CHECKLIST */
            .modules-section {
                width: 100%;
                max-width: 1200px;
                background: rgba(255,255,255,0.01);
                border-radius: 40px;
                padding: 60px 20px;
                margin-bottom: 80px;
                border: 1px solid rgba(255,255,255,0.05);
            }
            .module-tag {
                display: inline-block;
                padding: 8px 18px;
                background: rgba(56, 189, 248, 0.1);
                border: 1px solid rgba(56, 189, 248, 0.2);
                border-radius: 12px;
                margin: 5px;
                font-size: 0.9rem;
                color: #38bdf8;
            }

            /* CONTACTO BANNER */
            .contact-section {
                width: 100%;
                max-width: 1150px;
                padding: 80px 40px;
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                border-radius: 50px;
                box-shadow: 0 50px 100px rgba(0,0,0,0.5);
                border: 1px solid rgba(56, 189, 248, 0.2);
            }

            .dev-card {
                background: rgba(0,0,0,0.2);
                padding: 40px;
                border-radius: 30px;
                min-width: 320px;
                flex: 1;
                border: 1px solid rgba(255,255,255,0.05);
                transition: 0.3s;
            }
            .dev-card:hover { border-color: #22c55e; transform: scale(1.02); }

            .btn-wpp {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 12px;
                background: #22c55e;
                color: white !important;
                padding: 18px 30px;
                border-radius: 20px;
                text-decoration: none;
                font-weight: 800;
                font-size: 1.1rem;
                box-shadow: 0 15px 30px rgba(34, 197, 94, 0.3);
            }
        </style>

        <div class="landing-container">
            <div class="badge-new">Nueva Versión 9.12 Enterprise</div>
            <h1 class="main-title">Potencia tu Operación<br>Médica al 100%</h1>
            <p class="main-subtitle">La plataforma líder en gestión domiciliaria y ambulatoria. Control total sobre tu equipo, tus insumos y la seguridad legal de tus pacientes.</p>
            
            <div class="stats-container">
                <div class="stat-item"><span class="stat-num">100%</span><span class="stat-label">Digital</span></div>
                <div class="stat-item"><span class="stat-num">+50</span><span class="stat-label">Módulos</span></div>
                <div class="stat-item"><span class="stat-num">0%</span><span class="stat-label">Papel</span></div>
                <div class="stat-item"><span class="stat-num">GPS</span><span class="stat-label">Real Time</span></div>
            </div>

            <div class="grid-cards">
                <div class="glass-card">
                    <span class="card-icon">🛰️</span>
                    <h3 class="card-title">Geolocalización</h3>
                    <p class="card-text">Auditoría satelital de visitas. Sepa exactamente dónde y cuándo se realizó la atención con respaldo GPS inalterable.</p>
                </div>
                <div class="glass-card">
                    <span class="card-icon">📂</span>
                    <h3 class="card-title">Historia Clínica Unificada</h3>
                    <p class="card-text">Evoluciones multidisciplinarias (Médico, Enfermería, Kine) con adjunto de fotos de heridas y estudios.</p>
                </div>
                <div class="glass-card">
                    <span class="card-icon">💳</span>
                    <h3 class="card-title">Control de Caja y Honorarios</h3>
                    <p class="card-text">Liquidación automatizada de profesionales y control estricto de ingresos/egresos de la clínica.</p>
                </div>
                <div class="glass-card">
                    <span class="card-icon">🛡️</span>
                    <h3 class="card-title">Protección Jurídica</h3>
                    <p class="card-text">Consentimientos informados y recetas firmadas digitalmente con validez legal y exportación PDF inmediata.</p>
                </div>
            </div>

            <div class="modules-section">
                <h3 style="margin-bottom:30px;">Todo lo que tu empresa necesita</h3>
                <div class="module-tag">Pediatría PRO</div>
                <div class="module-tag">Telemedicina P2P</div>
                <div class="module-tag">Gestión de Stock</div>
                <div class="module-tag">Auditoría Médica</div>
                <div class="module-tag">Cierre Diario</div>
                <div class="module-tag">RRHH y Fichajes</div>
                <div class="module-tag">Balances Hídricos</div>
                <div class="module-tag">Escalas Clínicas</div>
                <div class="module-tag">Red de Profesionales</div>
            </div>

            <div class="contact-section">
                <h2 class="contact-title">¿Listo para escalar tu empresa de salud?</h2>
                <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 30px;">
                    <div class="dev-card">
                        <div style="color:#38bdf8; font-weight:800; margin-bottom:10px;">DIRECTOR TÉCNICO</div>
                        <div style="font-size:1.8rem; font-weight:900; margin-bottom:20px;">Enzo N. Girardi</div>
                        <a href="https://wa.me/5493584302024" target="_blank" class="btn-wpp">
                            SOPORTE TÉCNICO 📲
                        </a>
                    </div>
                    <div class="dev-card">
                        <div style="color:#38bdf8; font-weight:800; margin-bottom:10px;">DESARROLLO DE NEGOCIOS</div>
                        <div style="font-size:1.8rem; font-weight:900; margin-bottom:20px;">Dario Lanfranco</div>
                        <a href="https://wa.me/5493584201263" target="_blank" class="btn-wpp">
                            CONTRATACIONES 📲
                        </a>
                    </div>
                </div>
                <p style="margin-top:40px; color:#64748b;">MediCare Enterprise PRO © 2026 - Río Cuarto, Córdoba.</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🚀 ACCEDER AL SISTEMA AHORA", key="btn_ingresar_main", use_container_width=True):
        st.session_state.entered_app = True
        st.rerun()
    st.stop()
