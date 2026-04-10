import streamlit as st
import sys
from pathlib import Path
from importlib import import_module

# =====================================================================
# 1. CONFIGURACIÓN ESTRUCTURAL Y DE PÁGINA
# =====================================================================
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

st.set_page_config(
    page_title="MediCare PRO | Enterprise V9.12",
    page_icon="⚕️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =====================================================================
# 2. CARGA DE RECURSOS Y DEPENDENCIAS
# =====================================================================
try:
    from core import utils as core_utils
    from core.database import cargar_datos
    from core.auth import check_inactividad, render_login
except ImportError as e:
    st.error(f"❌ Error crítico de dependencias: {e}")
    st.stop()

# Inicialización del estado de la base de datos
if "_db_bootstrapped" not in st.session_state:
    core_utils.inicializar_db_state(cargar_datos() if cargar_datos else None)
    st.session_state["_db_bootstrapped"] = True

# =====================================================================
# 3. ESTILOS CSS ULTRA-PREMIUM (LANDING & APP)
# =====================================================================
GLOBAL_STYLES = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;800&display=swap');
    
    /* Fondo General Estilo SaaS */
    .stApp {
        background: radial-gradient(circle at 20% 20%, #0f172a 0%, #020617 100%) !important;
    }

    /* Contenedor Principal Landing */
    .landing-container {
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: #f8fafc;
        max-width: 1100px;
        margin: 0 auto;
        padding: 80px 20px;
        text-align: center;
    }

    /* Badges y Títulos */
    .hero-badge {
        background: rgba(56, 189, 248, 0.1);
        color: #38bdf8;
        padding: 8px 20px;
        border-radius: 100px;
        border: 1px solid rgba(56, 189, 248, 0.3);
        font-size: 0.85rem;
        font-weight: 700;
        letter-spacing: 1.5px;
        display: inline-block;
        margin-bottom: 30px;
        text-transform: uppercase;
    }

    .main-title {
        font-size: clamp(3rem, 7vw, 5rem);
        font-weight: 800;
        line-height: 1.1;
        background: linear-gradient(to right, #ffffff, #94a3b8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 25px;
    }

    .highlight { color: #38bdf8; -webkit-text-fill-color: #38bdf8; }

    /* Grid de Características */
    .grid-features {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 25px;
        margin: 60px 0;
    }

    .feature-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 24px;
        padding: 35px;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        text-align: left;
        backdrop-filter: blur(12px);
    }

    .feature-card:hover {
        background: rgba(56, 189, 248, 0.05);
        border-color: #38bdf8;
        transform: translateY(-10px);
        box-shadow: 0 20px 40px rgba(0,0,0,0.3);
    }

    .icon-box { font-size: 2.5rem; margin-bottom: 20px; display: block; }

    /* Grid de Contacto */
    .contact-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 25px;
        margin-top: 50px;
    }

    .contact-card {
        background: rgba(15, 23, 42, 0.8);
        padding: 30px;
        border-radius: 24px;
        border: 1px solid rgba(56, 189, 248, 0.2);
        text-align: center;
    }

    .btn-ws {
        display: block;
        background: #22c55e;
        color: white !important;
        text-decoration: none !important;
        padding: 15px;
        border-radius: 15px;
        font-weight: 700;
        margin-top: 20px;
        transition: 0.3s;
        box-shadow: 0 4px 15px rgba(34, 197, 94, 0.3);
    }

    .btn-ws:hover {
        background: #1eb050 !important;
        transform: scale(1.03);
    }

    /* Ocultar elementos nativos de Streamlit en Landing */
    div[data-testid="stToolbar"], [data-testid="stHeader"] {
        display: none !important;
    }
</style>
"""

# =====================================================================
# 4. LÓGICA DE NAVEGACIÓN Y RENDERIZADO
# =====================================================================
def render_current_view(tab_name, paciente_sel, mi_empresa, user, rol):
    # Diccionario de configuración de vistas (Optimizado)
    VIEW_CONFIG = {
        "Visitas y Agenda": ("views.visitas", "render_visitas"),
        "Dashboard": ("views.dashboard", "render_dashboard"),
        "Admision": ("views.admision", "render_admision"),
        "Clinica": ("views.clinica", "render_clinica"),
        "Evolucion": ("views.evolucion", "render_evolucion"),
        "RRHH y Fichajes": ("views.rrhh", "render_rrhh"),
        "Auditoria Legal": ("views.auditoria_legal", "render_auditoria_legal"),
    }

    if tab_name in VIEW_CONFIG:
        module_path, function_name = VIEW_CONFIG[tab_name]
        module = import_module(module_path)
        render_fn = getattr(module, function_name)
        
        # Ejecución dinámica según firma de función (Simplificado para el ejemplo)
        try:
            render_fn(paciente_sel, mi_empresa, user, rol)
        except TypeError:
            render_fn(paciente_sel, user, rol)

# =====================================================================
# 5. BODY DE LA APLICACIÓN
# =====================================================================

# ESTADO 1: LANDING PAGE PUBLICITARIA
if not st.session_state.get("entered_app", False):
    st.markdown(GLOBAL_STYLES, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="landing-container">
        <div class="hero-badge">SISTEMA MÉDICO DE ALTA PRECISIÓN</div>
        <h1 class="main-title">Escale su Operación <br><span class="highlight">Inteligente y Legal</span></h1>
        <p style="color:#94a3b8; font-size:1.2rem; max-width:800px; margin: 0 auto 40px;">
            La plataforma líder en gestión clínica. Control total sobre equipos, 
            trazabilidad legal de pacientes y geolocalización satelital.
        </p>

        <div class="grid-features">
            <div class="feature-card">
                <div class="icon-box">🛰️</div>
                <h4 style="color:white; margin-bottom:10px;">Geo-Auditoría</h4>
                <p style="font-size:0.9rem; color:#94a3b8;">Validación GPS en tiempo real para visitas domiciliarias y red de profesionales.</p>
            </div>
            <div class="feature-card">
                <div class="icon-box">🛡️</div>
                <h4 style="color:white; margin-bottom:10px;">Blindaje Jurídico</h4>
                <p style="font-size:0.9rem; color:#94a3b8;">Historias clínicas con firma digital biométrica y validez jurídica total.</p>
            </div>
            <div class="feature-card">
                <div class="icon-box">📈</div>
                <h4 style="color:white; margin-bottom:10px;">BI & Finanzas</h4>
                <p style="font-size:0.9rem; color:#94a3b8;">Liquidación automatizada de honorarios y balances financieros proyectados.</p>
            </div>
        </div>

        <div class="contact-grid">
            <div class="contact-card">
                <small style="color:#38bdf8; font-weight:700;">COMERCIAL Y NEGOCIOS</small>
                <h3 style="color:white; margin:10px 0;">Dario Lanfranco</h3>
                <a href="https://wa.me/5493584201263" class="btn-ws">Solicitar Cotización 🤝</a>
            </div>
            <div class="contact-card">
                <small style="color:#38bdf8; font-weight:700;">SOPORTE E INFRAESTRUCTURA</small>
                <h3 style="color:white; margin:10px 0;">Enzo N. Girardi</h3>
                <a href="https://wa.me/5493584302024" class="btn-ws">Soporte Técnico 📲</a>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Botón de entrada
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🚀 INGRESAR AL ECOSISTEMA", use_container_width=True):
            st.session_state.entered_app = True
            st.rerun()
    st.stop()

# ESTADO 2: LOGIN Y APLICACIÓN
if not st.session_state.get("authenticated", False):
    render_login() # Asumiendo que esta función maneja el estado 'authenticated'
else:
    # Una vez logueado, mostrar la interfaz de trabajo
    check_inactividad()
    st.sidebar.title("Navegación MediCare")
    # ... Resto de tu lógica de App ...
