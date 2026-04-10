import streamlit as st
import sys
from pathlib import Path
from importlib import import_module

# --- CONFIGURACIÓN ESTRUCTURAL ---
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Configuración de página (Debe ser lo primero)
st.set_page_config(
    page_title="MediCare PRO | Enterprise V9.12", 
    page_icon="⚕️",
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- CARGA DE RECURSOS ---
try:
    from core import utils as core_utils
    from core.database import cargar_datos
    from core.auth import check_inactividad
except ImportError as e:
    st.error(f"Error de sistema: {e}")
    st.stop()

# --- ESTILOS MEJORADOS (UI/UX) ---
LANDING_STYLES = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;800&display=swap');
    
    .stApp {
        background: radial-gradient(circle at 0% 0%, #0f172a 0%, #020617 100%) !important;
    }
    
    /* Animación de entrada */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .landing-container {
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: #f8fafc;
        max-width: 1100px;
        margin: 0 auto;
        padding: 60px 20px;
        animation: fadeIn 0.8s ease-out;
    }

    .hero-badge {
        background: rgba(56, 189, 248, 0.1);
        color: #38bdf8;
        padding: 6px 16px;
        border-radius: 100px;
        border: 1px solid rgba(56, 189, 248, 0.3);
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 1px;
        display: inline-block;
        margin-bottom: 24px;
    }

    .main-title {
        font-size: clamp(2.5rem, 6vw, 4.5rem);
        font-weight: 800;
        line-height: 1.1;
        margin-bottom: 20px;
        background: linear-gradient(to right, #ffffff, #94a3b8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .highlight { color: #38bdf8; -webkit-text-fill-color: #38bdf8; }

    .subtitle {
        color: #94a3b8;
        font-size: 1.2rem;
        max-width: 700px;
        margin: 0 auto 40px;
        line-height: 1.6;
    }

    .grid-features {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 20px;
        margin: 50px 0;
    }

    .feature-card {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 24px;
        padding: 30px;
        transition: all 0.3s ease;
        text-align: left;
    }

    .feature-card:hover {
        background: rgba(255, 255, 255, 0.05);
        border-color: rgba(56, 189, 248, 0.4);
        transform: translateY(-5px);
    }

    .icon-box {
        font-size: 2rem;
        margin-bottom: 15px;
        display: block;
    }

    .contact-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        margin-top: 40px;
    }

    .contact-card {
        background: linear-gradient(145deg, #0f172a, #1e293b);
        padding: 25px;
        border-radius: 20px;
        border: 1px solid rgba(255,255,255,0.1);
    }

    .btn-ws {
        display: block;
        background: #22c55e;
        color: white !important;
        text-decoration: none !important;
        padding: 12px;
        border-radius: 12px;
        font-weight: 600;
        margin-top: 15px;
        transition: 0.3s;
        text-align: center;
    }
    
    .btn-ws:hover { opacity: 0.9; transform: scale(1.02); }
</style>
"""

# --- LÓGICA DE LA LANDING ---
if not st.session_state.get("entered_app", False):
    st.markdown(LANDING_STYLES, unsafe_allow_html=True)
    
    with st.container():
        st.markdown(f"""
        <div class="landing-container">
            <div style="text-align:center;">
                <div class="hero-badge">NUEVA VERSIÓN 9.12 ENTERPRISE</div>
                <h1 class="main-title">Gestión Médica <br><span class="highlight">Inteligente y Legal</span></h1>
                <p class="subtitle">Potencie su clínica con la herramienta más robusta del mercado. Control de stock, geolocalización de visitas y blindaje jurídico en una sola plataforma.</p>
            </div>

            <div class="grid-features">
                <div class="feature-card">
                    <span class="icon-box">🛰️</span>
                    <h4 style="margin:0;">Geo-Auditoría</h4>
                    <p style="font-size:0.9rem; color:#64748b;">Seguimiento satelital en tiempo real de toda su red de profesionales.</p>
                </div>
                <div class="feature-card">
                    <span class="icon-box">🛡️</span>
                    <h4 style="margin:0;">Firma Biométrica</h4>
                    <p style="font-size:0.9rem; color:#64748b;">Validez legal total en recetas y consentimientos informados.</p>
                </div>
                <div class="feature-card">
                    <span class="icon-box">📊</span>
                    <h4 style="margin:0;">BI & Finanzas</h4>
                    <p style="font-size:0.9rem; color:#64748b;">Liquidación automática de honorarios y balances proyectados.</p>
                </div>
            </div>

            <div class="contact-grid">
                <div class="contact-card">
                    <small style="color:#38bdf8;">IMPLEMENTACIÓN</small>
                    <h3 style="margin:5px 0;">Dario Lanfranco</h3>
                    <a href="https://wa.me/5493584201263" class="btn-ws">Agendar Demo 🤝</a>
                </div>
                <div class="contact-card">
                    <small style="color:#38bdf8;">SOPORTE TÉCNICO</small>
                    <h3 style="margin:5px 0;">Enzo N. Girardi</h3>
                    <a href="https://wa.me/5493584302024" class="btn-ws">Consultas Técnicas 🛠️</a>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Botón de entrada principal
        cols = st.columns([1, 2, 1])
        with cols[1]:
            if st.button("🚀 ACCEDER AL ECOSISTEMA", use_container_width=True):
                st.session_state.entered_app = True
                st.rerun()
    st.stop()

# --- CONTINUACIÓN DE LA APP (LÓGICA DE RENDERIZADO) ---
# ... (Aquí va tu lógica de navegación de módulos)
