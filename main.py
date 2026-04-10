import streamlit as st
import sys
from pathlib import Path
from importlib import import_module

# 1. CONFIGURACIÓN INICIAL (Debe ser lo primero)
st.set_page_config(
    page_title="MediCare PRO | Enterprise V9.12",
    page_icon="⚕️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. DEFINICIÓN DE ESTILOS (CSS)
# He optimizado el CSS para que no haya conflictos de renderizado
ESTILOS_PREMIUM = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;800&display=swap');
    
    /* Fondo y Reset */
    .stApp {
        background: radial-gradient(circle at 20% 20%, #0f172a 0%, #020617 100%) !important;
    }
    
    .landing-wrapper {
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: #f8fafc;
        max-width: 1100px;
        margin: 0 auto;
        padding: 40px 10px;
        text-align: center;
    }

    .hero-badge {
        background: rgba(56, 189, 248, 0.1);
        color: #38bdf8;
        padding: 8px 20px;
        border-radius: 100px;
        border: 1px solid rgba(56, 189, 248, 0.3);
        font-size: 0.8rem;
        font-weight: 700;
        display: inline-block;
        margin-bottom: 20px;
        letter-spacing: 1px;
    }

    .main-title {
        font-size: clamp(2.5rem, 5vw, 4rem);
        font-weight: 800;
        line-height: 1.1;
        background: linear-gradient(to right, #ffffff, #94a3b8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 20px;
    }

    .highlight { color: #38bdf8; -webkit-text-fill-color: #38bdf8; }

    /* Grid de Features */
    .grid-features {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 20px;
        margin: 40px 0;
    }

    .feature-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 30px;
        text-align: left;
        transition: 0.3s ease;
    }

    .feature-card:hover {
        background: rgba(56, 189, 248, 0.05);
        border-color: #38bdf8;
        transform: translateY(-5px);
    }

    .icon-box { font-size: 2rem; margin-bottom: 15px; display: block; }

    /* Contact Grid */
    .contact-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 20px;
        margin-bottom: 30px;
    }

    .contact-card {
        background: rgba(15, 23, 42, 0.8);
        padding: 25px;
        border-radius: 20px;
        border: 1px solid rgba(56, 189, 248, 0.2);
    }

    .btn-ws {
        display: block;
        background: #22c55e;
        color: white !important;
        text-decoration: none !important;
        padding: 12px;
        border-radius: 12px;
        font-weight: 700;
        margin-top: 15px;
        transition: 0.3s;
        text-align: center;
    }

    /* Ocultar elementos de Streamlit en la Landing */
    #MainMenu, header, footer {visibility: hidden;}
</style>
"""

# 3. LÓGICA PRINCIPAL
if not st.session_state.get("entered_app", False):
    # Renderizamos el CSS
    st.markdown(ESTILOS_PREMIUM, unsafe_allow_html=True)
    
    # Renderizamos el HTML de la Landing
    st.markdown(f"""
    <div class="landing-wrapper">
        <div class="hero-badge">VERSION 9.12 ENTERPRISE PRO</div>
        <h1 class="main-title">Escale su Operación <br><span class="highlight">Inteligente y Legal</span></h1>
        <p style="color:#94a3b8; font-size:1.1rem; margin-bottom:40px;">
            Control total sobre equipos, insumos y trazabilidad legal de pacientes.
        </p>

        <div class="grid-features">
            <div class="feature-card">
                <span class="icon-box">🛰️</span>
                <h4 style="color:white; margin:0;">Geo-Auditoría</h4>
                <p style="font-size:0.9rem; color:#94a3b8; margin-top:10px;">
                    Validación GPS en tiempo real para visitas y red de profesionales.
                </p>
            </div>
            <div class="feature-card">
                <span class="icon-box">🛡️</span>
                <h4 style="color:white; margin:0;">Blindaje Jurídico</h4>
                <p style="font-size:0.9rem; color:#94a3b8; margin-top:10px;">
                    Historias clínicas con firma digital biométrica y validez total.
                </p>
            </div>
            <div class="feature-card">
                <span class="icon-box">📊</span>
                <h4 style="color:white; margin:0;">BI & Finanzas</h4>
                <p style="font-size:0.9rem; color:#94a3b8; margin-top:10px;">
                    Liquidación automatizada de honorarios y balances financieros.
                </p>
            </div>
        </div>

        <div class="contact-grid">
            <div class="contact-card">
                <small style="color:#38bdf8; font-weight:700;">COMERCIAL</small>
                <h3 style="color:white; margin:10px 0;">Dario Lanfranco</h3>
                <a href="https://wa.me/5493584201263" target="_blank" class="btn-ws">Solicitar Cotización 🤝</a>
            </div>
            <div class="contact-card">
                <small style="color:#38bdf8; font-weight:700;">TECNOLOGÍA</small>
                <h3 style="color:white; margin:10px 0;">Enzo N. Girardi</h3>
                <a href="https://wa.me/5493584302024" target="_blank" class="btn-ws">Soporte Técnico 📲</a>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Botón de entrada (Usando el botón nativo de Streamlit para la lógica)
    cols = st.columns([1, 1, 1])
    with cols[1]:
        if st.button("🚀 INGRESAR AL SISTEMA", use_container_width=True):
            st.session_state.entered_app = True
            st.rerun()
    st.stop()

# 4. ÁREA POST-LOGIN (Lo que sucede después de pulsar el botón)
else:
    st.title("Bienvenido al Panel de Control")
    if st.button("Cerrar Sesión"):
        st.session_state.entered_app = False
        st.rerun()
