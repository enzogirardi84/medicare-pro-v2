import base64
import os
import sys
from html import escape
from importlib import import_module
from pathlib import Path

import streamlit as st

from core.auth import check_inactividad, render_login
from core.utils import cargar_texto_asset, inicializar_db_state, obtener_alertas_clinicas, tiene_permiso

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="MediCare Enterprise PRO V9.12", layout="wide", initial_sidebar_state="collapsed")

try:
    st.markdown(f"<style>{cargar_texto_asset('style.css')}</style>", unsafe_allow_html=True)
except Exception:
    pass

inicializar_db_state(None)

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

VIEW_ROLE_RULES = {
    "Visitas y Agenda": ["Operativo", "Medico", "Enfermeria", "Coordinador"],
    "Dashboard": ["Coordinador"],
    "Admision": ["Administrativo", "Coordinador"],
    "Clinica": ["Operativo", "Medico", "Enfermeria", "Coordinador"],
    "Pediatria": ["Operativo", "Medico", "Enfermeria", "Coordinador"],
    "Evolucion": ["Operativo", "Medico", "Enfermeria", "Coordinador"],
    "Estudios": ["Operativo", "Medico", "Enfermeria", "Coordinador"],
    "Materiales": ["Operativo", "Enfermeria", "Coordinador"],
    "Recetas": ["Operativo", "Medico", "Enfermeria", "Coordinador"],
    "Balance": ["Operativo", "Medico", "Enfermeria", "Coordinador"],
    "Inventario": ["Administrativo", "Coordinador"],
    "Caja": ["Administrativo", "Coordinador"],
    "Emergencias y Ambulancia": ["Operativo", "Medico", "Enfermeria", "Coordinador"],
    "Red de Profesionales": ["Administrativo", "Coordinador"],
    "Escalas Clinicas": ["Operativo", "Medico", "Enfermeria", "Coordinador"],
    "Historial": ["Operativo", "Medico", "Enfermeria", "Coordinador"],
    "PDF": ["Operativo", "Medico", "Enfermeria", "Coordinador"],
    "Telemedicina": ["Operativo", "Medico", "Enfermeria", "Coordinador"],
    "Cierre Diario": ["Coordinador"],
    "Mi Equipo": ["Coordinador"],
    "Asistencia en Vivo": ["Coordinador"],
    "RRHH y Fichajes": ["Coordinador"],
    "Auditoria": ["Auditoria", "Coordinador"],
    "Auditoria Legal": ["Auditoria", "Coordinador"],
}

VIEW_LABELS = {
    "Visitas y Agenda": "📍 Visitas y Agenda",
    "Dashboard": "📊 Dashboard",
    "Admision": "🧾 Admision",
    "Clinica": "🩺 Clinica",
    "Pediatria": "👶 Pediatria",
    "Evolucion": "✍️ Evolucion",
    "Estudios": "🧪 Estudios",
    "Materiales": "📦 Materiales",
    "Recetas": "💊 Recetas",
    "Balance": "💧 Balance",
    "Inventario": "🏥 Inventario",
    "Caja": "💵 Caja",
    "Emergencias y Ambulancia": "🚑 Emergencias y Ambulancia",
    "Escalas Clinicas": "📏 Escalas Clinicas",
    "Historial": "🗂️ Historial",
    "PDF": "📄 PDF",
    "Telemedicina": "🎥 Telemedicina",
    "Cierre Diario": "🧮 Cierre Diario",
    "Mi Equipo": "👥 Mi Equipo",
    "Asistencia en Vivo": "🛰️ Asistencia en Vivo",
    "RRHH y Fichajes": "⏱️ RRHH y Fichajes",
    "Auditoria": "🔎 Auditoria",
    "Auditoria Legal": "⚖️ Auditoria Legal",
}


VIEW_LABELS = {
    "Visitas y Agenda": "\U0001F4CD Visitas y Agenda",
    "Dashboard": "\U0001F4CA Dashboard",
    "Admision": "\U0001FA7E Admision",
    "Clinica": "\U0001FA7A Clinica",
    "Pediatria": "\U0001F476 Pediatria",
    "Evolucion": "\u270D\ufe0f Evolucion",
    "Estudios": "\U0001F9EA Estudios",
    "Materiales": "\U0001F4E6 Materiales",
    "Recetas": "\U0001F48A Recetas",
    "Balance": "\U0001F4A7 Balance",
    "Inventario": "\U0001F3E5 Inventario",
    "Caja": "\U0001F4B5 Caja",
    "Emergencias y Ambulancia": "\U0001F691 Emergencias y Ambulancia",
    "Red de Profesionales": "\U0001F91D Red de Profesionales",
    "Escalas Clinicas": "\U0001F4CF Escalas Clinicas",
    "Historial": "\U0001F5C2\ufe0f Historial",
    "PDF": "\U0001F4C4 PDF",
    "Telemedicina": "\U0001F3A5 Telemedicina",
    "Cierre Diario": "\U0001F9EE Cierre Diario",
    "Mi Equipo": "\U0001F465 Mi Equipo",
    "Asistencia en Vivo": "\U0001F6F0\ufe0f Asistencia en Vivo",
    "RRHH y Fichajes": "\u23F1\ufe0f RRHH y Fichajes",
    "Auditoria": "\U0001F50E Auditoria",
    "Auditoria Legal": "\u2696\ufe0f Auditoria Legal",
}

VIEW_NAV_LABELS = {
    "Visitas y Agenda": "📍 Visitas",
    "Dashboard": "📊 Dashboard",
    "Admision": "🧾 Admision",
    "Clinica": "🩺 Clinica",
    "Pediatria": "👶 Pediatria",
    "Evolucion": "✍️ Evolucion",
    "Estudios": "🧪 Estudios",
    "Materiales": "📦 Materiales",
    "Recetas": "💊 Recetas",
    "Balance": "💧 Balance",
    "Inventario": "🏥 Inventario",
    "Caja": "💵 Caja",
    "Emergencias y Ambulancia": "🚑 Emergencias",
    "Enfermeria": "🩹 Enfermeria",
    "Escalas Clinicas": "📏 Escalas",
    "Historial": "🗂️ Historial",
    "PDF": "📄 PDF",
    "Telemedicina": "🎥 Telemedicina",
    "Cierre Diario": "🧮 Cierre",
    "Mi Equipo": "👥 Equipo",
    "Asistencia en Vivo": "🛰️ Asistencia",
    "RRHH y Fichajes": "⏱️ RRHH",
    "Auditoria": "🔎 Auditoria",
    "Auditoria Legal": "⚖️ Legal",
}

def render_current_view(tab_name, paciente_sel, mi_empresa, user, rol):
    if not tiene_permiso(rol, VIEW_ROLE_RULES.get(tab_name)):
        st.error("No tienes permisos para acceder a este modulo.")
        return
    module_name, function_name = VIEW_CONFIG[tab_name]
    render_fn = getattr(import_module(module_name), function_name)

    if tab_name == "Visitas y Agenda":
        render_fn(paciente_sel, mi_empresa, user, rol)
    elif tab_name == "Admision":
        render_fn(mi_empresa, rol)
    elif tab_name == "Clinica":
        render_fn(paciente_sel)
    elif tab_name == "Pediatria":
        render_fn(paciente_sel, user)
    elif tab_name == "Evolucion":
        render_fn(paciente_sel, user, rol)
    elif tab_name == "Estudios":
        render_fn(paciente_sel, user, rol)
    elif tab_name == "Materiales":
        render_fn(paciente_sel, mi_empresa, user)
    elif tab_name == "Recetas":
        render_fn(paciente_sel, mi_empresa, user, rol)
    elif tab_name == "Balance":
        render_fn(paciente_sel, user)
    elif tab_name == "Inventario":
        render_fn(mi_empresa)
    elif tab_name == "Caja":
        render_fn(paciente_sel, mi_empresa, user, rol)
    elif tab_name == "Emergencias y Ambulancia":
        render_fn(paciente_sel, mi_empresa, user)
    elif tab_name == "Red de Profesionales":
        render_fn(mi_empresa, user, rol)
    elif tab_name == "Escalas Clinicas":
        render_fn(paciente_sel, user)
    elif tab_name == "Historial":
        render_fn(paciente_sel)
    elif tab_name == "PDF":
        render_fn(paciente_sel, mi_empresa, user, rol)
    elif tab_name == "Telemedicina":
        render_fn(paciente_sel)
    elif tab_name == "Dashboard":
        render_fn(mi_empresa, rol)
    elif tab_name == "Cierre Diario":
        render_fn(mi_empresa, user)
    elif tab_name == "Mi Equipo":
        render_fn(mi_empresa, rol)
    elif tab_name == "Asistencia en Vivo":
        render_fn(mi_empresa, user)
    elif tab_name == "RRHH y Fichajes":
        render_fn(mi_empresa, rol, user)
    elif tab_name == "Auditoria":
        render_fn(mi_empresa, user)
    elif tab_name == "Auditoria Legal":
        render_fn(mi_empresa, user)


def resolve_current_view(menu):
    vista_actual = st.session_state.get("modulo_actual", menu[0])
    if vista_actual not in menu:
        vista_actual = menu[0]
    st.session_state["modulo_actual"] = vista_actual
    return vista_actual


def _compact_patient_label(nombre, estado):
    nombre = str(nombre or "").strip()
    sufijo = " [ALTA]" if estado == "De Alta" else ""
    limite = 34 if sufijo else 40
    if len(nombre) > limite:
        nombre = f"{nombre[:limite - 1].rstrip()}…"
    return f"{nombre}{sufijo}"


def _sidebar_patient_card(paciente_sel, detalles):
    return f"""
    <div class="mc-patient-card">
        <div class="mc-patient-card-kicker">Paciente activo</div>
        <div class="mc-patient-card-name">{escape(paciente_sel)}</div>
        <div class="mc-patient-card-meta">
            DNI: {escape(detalles.get('dni', 'S/D'))}<br>
            OS: {escape(detalles.get('obra_social', 'S/D'))}<br>
            Estado: {escape(detalles.get('estado', 'Activo'))}
        </div>
    </div>
    """


def render_module_nav(menu, vista_actual):
    st.markdown(
        """
        <section class="mc-module-shell" aria-label="Navegacion principal de modulos">
            <div class="mc-module-shell-head">
                <span class="mc-module-shell-kicker">Navegacion</span>
                <h3 class="mc-module-shell-title">Modulos del sistema</h3>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    selected = st.pills(
        "Modulos del sistema",
        menu,
        default=vista_actual,
        selection_mode="single",
        format_func=lambda x: VIEW_NAV_LABELS.get(x, x),
        label_visibility="collapsed",
        key="module_nav_pills",
    )
    if selected and selected != vista_actual:
        st.session_state["modulo_actual"] = selected
        return selected
    return selected or vista_actual


if "entered_app" not in st.session_state:
    st.session_state.entered_app = False


def limpiar_sesion_app():
    claves = [
        "logeado",
        "u_actual",
        "ultima_actividad",
        "modulo_actual",
        "paciente_actual",
        "entered_app",
    ]
    for clave in claves:
        st.session_state.pop(clave, None)
    st.session_state["entered_app"] = False


def obtener_logo_landing():
    posibles = [
        Path(__file__).resolve().parent / "assets" / "logo_medicare_pro.jpeg",
        Path(__file__).resolve().parent / "assets" / "logo_medicare_pro.jpg",
        Path(__file__).resolve().parent / "assets" / "logo_medicare_pro.png",
        Path(__file__).resolve().parent / "logo_medicare_pro.jpeg",
        Path(__file__).resolve().parent / "logo_medicare_pro.jpg",
        Path(__file__).resolve().parent / "logo_medicare_pro.png",
    ]
    for ruta in posibles:
        if ruta.exists():
            mime = "image/png" if ruta.suffix.lower() == ".png" else "image/jpeg"
            encoded = base64.b64encode(ruta.read_bytes()).decode()
            return f"<img src='data:{mime};base64,{encoded}' style='height: 112px; border-radius: 22px; box-shadow: 0 15px 35px rgba(0,0,0,0.45), 0 0 24px rgba(56,189,248,0.25); margin-bottom: 24px;'>"

    svg = """
    <svg xmlns='http://www.w3.org/2000/svg' width='320' height='160' viewBox='0 0 320 160'>
      <defs>
        <linearGradient id='g1' x1='0%' y1='0%' x2='100%' y2='100%'>
          <stop offset='0%' stop-color='#38bdf8'/>
          <stop offset='100%' stop-color='#2563eb'/>
        </linearGradient>
      </defs>
      <rect x='18' y='18' width='284' height='124' rx='28' fill='#08111f'/>
      <rect x='26' y='26' width='268' height='108' rx='24' fill='url(#g1)' opacity='0.12'/>
      <circle cx='84' cy='80' r='30' fill='url(#g1)'/>
      <path d='M74 80h20M84 70v20' stroke='#fff' stroke-width='8' stroke-linecap='round'/>
      <text x='128' y='72' fill='#f8fafc' font-size='26' font-family='Inter, Arial, sans-serif' font-weight='700'>MediCare</text>
      <text x='128' y='102' fill='#94a3b8' font-size='18' font-family='Inter, Arial, sans-serif' font-weight='600'>Enterprise PRO</text>
    </svg>
    """
    encoded = base64.b64encode(svg.encode("utf-8")).decode()
    return f"<img src='data:image/svg+xml;base64,{encoded}' style='height: 112px; margin-bottom: 24px;'>"


def obtener_folleto_landing():
    posibles = [
        Path(__file__).resolve().parent / "marketing" / "Folleto_Comercial_MediCare_Enterprise_PRO.pdf",
        Path(__file__).resolve().parent / "marketing" / "folleto_comercial.pdf",
    ]
    for ruta in posibles:
        if ruta.exists():
            return ruta
    return None

if not st.session_state.entered_app:
    logo_html = obtener_logo_landing()
    st.markdown(
        """
        <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            html, body, .stApp { overflow-x: hidden !important; }
            .block-container { padding-top: 0rem !important; padding-bottom: 0rem !important; max-width: 100% !important; margin-top: 0 !important; overflow: visible !important; }
            .stApp { background-color: #020617 !important; background-image: radial-gradient(circle at top right, #1e293b 0%, #020617 80%) !important; }
            div.stButton { display: flex; justify-content: center; margin-top: 26px; padding-bottom: 50px; }
            div.stButton > button {
                background: linear-gradient(135deg, #0ea5e9 0%, #4f46e5 100%) !important;
                color: white !important; font-size: 1.2rem !important; font-weight: 900 !important;
                padding: 16px 55px !important; border-radius: 9999px !important;
                border: 1px solid rgba(255,255,255,0.28) !important;
                box-shadow: 0 10px 30px rgba(14, 165, 233, 0.45) !important;
                transition: all 0.3s ease !important; text-transform: uppercase; letter-spacing: 2px;
            }
            div.stButton > button:hover {
                transform: translateY(-4px) !important;
                box-shadow: 0 15px 40px rgba(99, 102, 241, 0.65) !important;
                background: linear-gradient(135deg, #38bdf8 0%, #6366f1 100%) !important;
            }
            div.stDownloadButton { display: flex; justify-content: center; margin-top: 18px; }
            div.stDownloadButton > button {
                background: linear-gradient(135deg, #14b8a6 0%, #22c55e 50%, #38bdf8 100%) !important;
                color: white !important;
                font-size: 1.05rem !important;
                font-weight: 900 !important;
                padding: 16px 30px !important;
                border-radius: 20px !important;
                border: 1px solid rgba(255,255,255,0.28) !important;
                box-shadow: 0 18px 38px rgba(20, 184, 166, 0.26), 0 0 0 1px rgba(255,255,255,0.04) inset !important;
                transition: all 0.25s ease !important;
                min-width: 390px !important;
                letter-spacing: 0.2px !important;
            }
            div.stDownloadButton > button:hover {
                transform: translateY(-3px) scale(1.01) !important;
                box-shadow: 0 22px 44px rgba(34,197,94,0.34), 0 0 28px rgba(56,189,248,0.18) !important;
                filter: brightness(1.06);
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    html_lines = [
        "<style>",
        "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap');",
        ".landing-page { font-family: 'Inter', sans-serif; color: #f8fafc; display: flex; flex-direction: column; align-items: center; padding: 58px 20px 46px; position: relative; isolation: isolate; }",
        ".landing-page::before { content: ''; position: absolute; width: 380px; height: 380px; top: 20px; left: 6%; background: radial-gradient(circle, rgba(14,165,233,0.22) 0%, rgba(14,165,233,0) 70%); filter: blur(16px); z-index: -1; }",
        ".landing-page::after { content: ''; position: absolute; width: 420px; height: 420px; top: 120px; right: 4%; background: radial-gradient(circle, rgba(99,102,241,0.18) 0%, rgba(99,102,241,0) 70%); filter: blur(18px); z-index: -1; }",
        ".logo-shell { background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(241,245,249,0.94)); padding: 18px 20px; border-radius: 30px; box-shadow: 0 18px 46px rgba(14,165,233,0.20), 0 0 0 1px rgba(255,255,255,0.45) inset; margin-bottom: 28px; }",
        ".title { font-size: clamp(2.5rem, 6vw, 4.2rem); font-weight: 900; line-height: 1.03; margin: 0 0 18px; text-align: center; letter-spacing: -1.4px; text-shadow: 0 10px 30px rgba(2,6,23,0.18); }",
        ".title-glow { background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }",
        ".subtitle { font-size: 1.18rem; color: #cbd5e1; font-weight: 400; margin: 0 0 38px; max-width: 820px; text-align: center; line-height: 1.78; }",
        ".grid-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 28px; max-width: 1220px; width: 100%; margin-bottom: 72px; }",
        ".glass-card-pro { background: linear-gradient(145deg, rgba(24, 36, 61, 0.52) 0%, rgba(15, 23, 42, 0.94) 100%); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.07); border-radius: 28px; padding: 40px 30px; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); text-align: left; box-shadow: 0 10px 30px rgba(0,0,0,0.22); min-height: 238px; }",
        ".glass-card-pro:hover { transform: translateY(-8px); border-color: rgba(56, 189, 248, 0.45); box-shadow: 0 20px 40px rgba(0,0,0,0.35), 0 0 25px rgba(56,189,248,0.12); }",
        ".icon-box-pro { font-size: 2.35rem; margin-bottom: 22px; background: linear-gradient(135deg, rgba(56,189,248,0.14), rgba(14,165,233,0.05)); width: 82px; height: 82px; display: flex; align-items: center; justify-content: center; border-radius: 22px; border: 1px solid rgba(56,189,248,0.23); }",
        ".card-title-pro { font-size: 1.38rem; font-weight: 800; margin-bottom: 14px; color: #ffffff; letter-spacing: -0.5px; }",
        ".card-text-pro { color: #cbd5e1; font-size: 0.98rem; line-height: 1.7; margin: 0; font-weight: 400; }",
        ".contact-section-pro { max-width: 1040px; width: 100%; text-align: center; background: linear-gradient(145deg, rgba(13, 21, 44, 0.92), rgba(2, 6, 23, 0.99)); border: 1px solid rgba(56, 189, 248, 0.24); border-radius: 40px; padding: 56px 36px; box-shadow: 0 24px 52px rgba(0,0,0,0.28); position: relative; overflow: hidden; }",
        ".contact-section-pro::before { content: ''; position: absolute; width: 280px; height: 280px; right: -80px; top: -60px; background: radial-gradient(circle, rgba(56,189,248,0.15) 0%, rgba(56,189,248,0) 72%); pointer-events: none; }",
        ".contact-grid-pro { display: flex; flex-wrap: wrap; justify-content: center; gap: 36px; margin-top: 34px; }",
        ".contact-profile-pro { flex: 1; min-width: 280px; max-width: 420px; background: linear-gradient(145deg, rgba(24, 36, 61, 0.58), rgba(15, 23, 42, 0.8)); padding: 36px 26px; border-radius: 26px; border: 1px solid rgba(255, 255, 255, 0.06); transition: 0.3s; box-shadow: inset 0 0 0 1px rgba(56,189,248,0.06), 0 12px 28px rgba(0,0,0,0.16); }",
        ".contact-profile-pro:hover { background: linear-gradient(145deg, rgba(30, 41, 59, 0.68), rgba(15, 23, 42, 0.9)); border-color: rgba(56, 189, 248, 0.34); transform: translateY(-4px); }",
        ".p-name { font-size: 1.46rem; font-weight: 700; color: #ffffff; margin: 0 0 8px; }",
        ".p-role { font-size: 0.82rem; color: #38bdf8; text-transform: uppercase; letter-spacing: 1.6px; font-weight: 800; margin: 0 0 28px; line-height: 1.45; }",
        ".btn-flex-pro { display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; }",
        ".btn-link-pro { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 15px 24px; border-radius: 16px; text-decoration: none; font-weight: 800; font-size: 0.95rem; transition: all 0.3s; min-width: 166px; color: white !important; }",
        ".wpp-pro { background: linear-gradient(135deg, #22c55e, #16a34a); box-shadow: 0 4px 15px rgba(34,197,94,0.28); }",
        ".wpp-pro:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(34,197,94,0.42); filter: brightness(1.08); }",
        ".mail-pro { background: linear-gradient(135deg, #3b82f6, #2563eb); box-shadow: 0 4px 15px rgba(59,130,246,0.28); }",
        ".mail-pro:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(59,130,246,0.42); filter: brightness(1.08); }",
        ".trust-strip { max-width: 1180px; width: 100%; display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin: 0 0 36px; }",
        ".trust-pill { padding: 12px 18px; border-radius: 999px; background: linear-gradient(145deg, rgba(15, 23, 42, 0.92), rgba(30, 41, 59, 0.82)); border: 1px solid rgba(148, 163, 184, 0.16); color: #f8fafc; font-size: 0.92rem; font-weight: 700; box-shadow: 0 10px 22px rgba(2,6,23,0.18), inset 0 1px 0 rgba(255,255,255,0.06); }",
        ".spotlight-grid { max-width: 1180px; width: 100%; display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 24px; margin: 0 0 32px; }",
        ".spotlight-card { background: linear-gradient(145deg, rgba(15, 23, 42, 0.94), rgba(11, 18, 32, 0.98)); border: 1px solid rgba(56, 189, 248, 0.18); border-radius: 32px; padding: 32px 32px 30px; box-shadow: 0 24px 50px rgba(0,0,0,0.26), inset 0 1px 0 rgba(255,255,255,0.04); position: relative; overflow: hidden; }",
        ".spotlight-card::after { content: ''; position: absolute; inset: 0; background: linear-gradient(135deg, rgba(56,189,248,0.06), rgba(99,102,241,0.02) 45%, rgba(0,0,0,0) 70%); pointer-events: none; }",
        ".spotlight-kicker { color: #38bdf8; font-size: 0.78rem; letter-spacing: 2px; font-weight: 800; text-transform: uppercase; margin: 0 0 14px; }",
        ".spotlight-title { color: #ffffff; font-size: 2rem; font-weight: 900; line-height: 1.15; margin: 0 0 14px; }",
        ".spotlight-text { color: #cbd5e1; font-size: 1rem; line-height: 1.8; margin: 0; }",
        ".check-list { display: grid; gap: 12px; margin-top: 22px; }",
        ".check-item { color: #e2e8f0; font-size: 0.96rem; line-height: 1.6; padding: 13px 15px; border-radius: 18px; background: linear-gradient(145deg, rgba(30, 41, 59, 0.56), rgba(15, 23, 42, 0.66)); border: 1px solid rgba(56, 189, 248, 0.12); box-shadow: inset 0 1px 0 rgba(255,255,255,0.03); }",
        ".benefit-band { max-width: 1180px; width: 100%; background: linear-gradient(145deg, rgba(10, 16, 30, 0.98), rgba(15, 23, 42, 0.99)); border-radius: 34px; border: 1px solid rgba(148, 163, 184, 0.12); padding: 36px 32px; margin: 0 0 54px; box-shadow: 0 24px 48px rgba(0,0,0,0.22); }",
        ".benefit-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 20px; }",
        ".benefit-card { padding: 22px 20px; border-radius: 24px; background: linear-gradient(145deg, rgba(30, 41, 59, 0.5), rgba(15, 23, 42, 0.72)); border: 1px solid rgba(56, 189, 248, 0.10); box-shadow: 0 10px 24px rgba(0,0,0,0.14); }",
        ".benefit-card h5 { margin: 0 0 8px; color: #ffffff; font-size: 1rem; font-weight: 800; }",
        ".benefit-card p { margin: 0; color: #cbd5e1; font-size: 0.92rem; line-height: 1.6; }",
        ".segment-grid { max-width: 1180px; width: 100%; display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 18px; margin: 0 0 48px; }",
        ".segment-card { padding: 28px 24px; border-radius: 28px; background: linear-gradient(145deg, rgba(22, 32, 55, 0.84), rgba(8, 15, 30, 0.98)); border: 1px solid rgba(56, 189, 248, 0.12); box-shadow: 0 16px 30px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.03); }",
        ".segment-card h4 { margin: 0 0 12px; color: #ffffff; font-size: 1.15rem; font-weight: 800; }",
        ".segment-card p { margin: 0; color: #cbd5e1; font-size: 0.95rem; line-height: 1.7; }",
        ".closing-banner { max-width: 1180px; width: 100%; display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 24px; margin: 0 0 42px; }",
        ".closing-panel { padding: 32px 30px; border-radius: 32px; background: linear-gradient(135deg, rgba(14, 165, 233, 0.18), rgba(79, 70, 229, 0.22)); border: 1px solid rgba(99, 102, 241, 0.24); box-shadow: 0 20px 44px rgba(0,0,0,0.2); }",
        ".closing-panel h3 { margin: 0 0 12px; color: #ffffff; font-size: 1.75rem; font-weight: 900; }",
        ".closing-panel p { margin: 0; color: #dbeafe; font-size: 1rem; line-height: 1.8; }",
        ".brochure-band { max-width: 1040px; width: 100%; margin: 0 0 34px; padding: 36px 32px; border-radius: 34px; background: linear-gradient(145deg, rgba(6, 16, 34, 0.98), rgba(15, 23, 42, 0.92)); border: 1px solid rgba(56, 189, 248, 0.22); box-shadow: 0 28px 58px rgba(0,0,0,0.24); text-align: center; position: relative; overflow: hidden; }",
        ".brochure-band::before { content: ''; position: absolute; width: 220px; height: 220px; left: -70px; top: -70px; background: radial-gradient(circle, rgba(34,197,94,0.18) 0%, rgba(34,197,94,0) 70%); }",
        ".brochure-band::after { content: ''; position: absolute; width: 240px; height: 240px; right: -90px; bottom: -120px; background: radial-gradient(circle, rgba(56,189,248,0.16) 0%, rgba(56,189,248,0) 74%); }",
        ".brochure-kicker { position: relative; margin: 0 0 10px; color: #6ee7b7; text-transform: uppercase; letter-spacing: 2px; font-size: 0.78rem; font-weight: 800; }",
        ".brochure-title { position: relative; margin: 0 0 12px; color: #ffffff; font-size: 2.15rem; font-weight: 900; letter-spacing: -1px; text-shadow: 0 10px 28px rgba(2,6,23,0.24); }",
        ".brochure-text { position: relative; margin: 0 auto; max-width: 760px; color: #cbd5e1; font-size: 1rem; line-height: 1.8; }",
        ".brochure-badges { position: relative; display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-top: 18px; }",
        ".brochure-badge { padding: 10px 14px; border-radius: 999px; background: rgba(15,23,42,0.64); border: 1px solid rgba(255,255,255,0.08); color: #e2e8f0; font-size: 0.88rem; font-weight: 700; box-shadow: inset 0 1px 0 rgba(255,255,255,0.04); }",
        "@media (max-width: 900px) { .spotlight-grid, .closing-banner { grid-template-columns: 1fr; } }",
        "@media (max-width: 768px) { .landing-page { padding: 42px 18px 28px; } .landing-page::before, .landing-page::after { width: 220px; height: 220px; } .grid-cards { gap: 20px; margin-bottom: 40px; } .glass-card-pro { padding: 28px 22px; min-height: auto; } .contact-section-pro { padding: 38px 18px; border-radius: 28px; } .contact-grid-pro { gap: 20px; } .benefit-band { padding: 28px 20px; } .trust-strip { justify-content: flex-start; } .spotlight-card, .segment-card, .closing-panel, .brochure-band { padding: 24px 20px; } .spotlight-title, .brochure-title { font-size: 1.75rem; } div.stDownloadButton > button { min-width: 100% !important; width: 100% !important; } }",
        "</style>",
        "<div class='landing-page'>",
        f"<div class='logo-shell'>{logo_html}</div>",
        "<h1 class='title'>Gestion clinica, operativa y legal <br><span class='title-glow'>en una sola plataforma</span></h1>",
        "<p class='subtitle'>MediCare Enterprise PRO ordena pacientes, visitas, evoluciones, recetas, firmas, emergencias, auditoria y personal en una app pensada para empresas, coordinacion y profesionales de salud.</p>",
        "<div class='trust-strip'>",
        "<div class='trust-pill'>Historia clinica digital</div>",
        "<div class='trust-pill'>Fichada GPS</div>",
        "<div class='trust-pill'>Recetas y consentimientos con firma</div>",
        "<div class='trust-pill'>Auditoria legal</div>",
        "<div class='trust-pill'>Emergencias y ambulancia</div>",
        "<div class='trust-pill'>Roles por usuario</div>",
        "</div>",
        "<div class='spotlight-grid'>",
        "<div class='spotlight-card'>",
        "<p class='spotlight-kicker'>Pensado para salud real</p>",
        "<h3 class='spotlight-title'>Si hoy trabajas entre papel, WhatsApp y planillas, estas perdiendo control y respaldo</h3>",
        "<p class='spotlight-text'>Cuando la informacion queda dispersa aumentan los errores, se complica la coordinacion y se debilita el soporte frente a auditorias, familiares o instituciones. MediCare Enterprise PRO centraliza el trabajo clinico y operativo para que todo quede registrado, ordenado y listo para mostrar.</p>",
        "</div>",
        "<div class='spotlight-card'>",
        "<p class='spotlight-kicker'>Diferencial comercial</p>",
        "<h3 class='spotlight-title'>Todo lo que necesita tu operacion de salud en una sola app</h3>",
        "<div class='check-list'>",
        "<div class='check-item'>Visitas, agenda y trazabilidad diaria para equipos en calle.</div>",
        "<div class='check-item'>Historia clinica, signos vitales, estudios y escalas en tiempo real.</div>",
        "<div class='check-item'>Recetas, consentimientos y respaldo PDF con enfoque legal.</div>",
        "<div class='check-item'>Control de personal, coordinacion, auditoria y RRHH.</div>",
        "</div>",
        "</div>",
        "</div>",
        "<div class='brochure-band'>",
        "<p class='brochure-kicker'>Material comercial listo para enviar</p>",
        "<h3 class='brochure-title'>Descarga una presentacion profesional de la app</h3>",
        "<p class='brochure-text'>Comparte un PDF comercial con modulos, beneficios, propuesta de valor y enfoque clinico-operativo para mostrar MediCare Enterprise PRO en reuniones, WhatsApp o presentaciones con potenciales clientes.</p>",
        "<div class='brochure-badges'><span class='brochure-badge'>Presentacion institucional</span><span class='brochure-badge'>Beneficios claros</span><span class='brochure-badge'>Ideal para WhatsApp y reuniones</span></div>",
        "</div>",
        "<div class='grid-cards'>",
        "<div class='glass-card-pro'><div class='icon-box-pro'>📍</div><h4 class='card-title-pro'>Fichaje GPS</h4><p class='card-text-pro'>Control de asistencia verificado por coordenadas exactas del domicilio del paciente.</p></div>",
        "<div class='glass-card-pro'><div class='icon-box-pro'>📄</div><h4 class='card-title-pro'>Evolución Médica</h4><p class='card-text-pro'>Carga digital al instante de signos vitales, parámetros y fotografías clínicas.</p></div>",
        "<div class='glass-card-pro'><div class='icon-box-pro'>💊</div><h4 class='card-title-pro'>Stock Inteligente</h4><p class='card-text-pro'>Gestión de inventario en tiempo real con descuento automático por cada práctica.</p></div>",
        "<div class='glass-card-pro'><div class='icon-box-pro'>✍️</div><h4 class='card-title-pro'>Firma Digital</h4><p class='card-text-pro'>Recetas y consentimientos validados con firma biométrica directamente en pantalla.</p></div>",
        "<div class='glass-card-pro'><div class='icon-box-pro'>📹</div><h4 class='card-title-pro'>Telemedicina</h4><p class='card-text-pro'>Videollamadas P2P seguras, integradas nativamente al historial del paciente.</p></div>",
        "<div class='glass-card-pro'><div class='icon-box-pro'>👶</div><h4 class='card-title-pro'>Pediatría</h4><p class='card-text-pro'>Control de crecimiento exhaustivo y gráficas de percentiles 100% automatizadas.</p></div>",
        "<div class='glass-card-pro'><div class='icon-box-pro'>💧</div><h4 class='card-title-pro'>Balance Hídrico</h4><p class='card-text-pro'>Cálculo estricto de ingresos y egresos con alertas preventivas por retención.</p></div>",
        "<div class='glass-card-pro'><div class='icon-box-pro'>📋</div><h4 class='card-title-pro'>Auditoría RRHH</h4><p class='card-text-pro'>Cierres diarios detallados, reportes de desempeño y liquidación de servicios.</p></div>",
        "</div>",
        "<div class='benefit-band'>",
        "<p class='spotlight-kicker'>Por que elegir MediCare Enterprise PRO</p>",
        "<h3 class='spotlight-title' style='font-size: 1.9rem;'>Una plataforma pensada para trabajar mejor y vender un servicio mas profesional</h3>",
        "<div class='benefit-grid'>",
        "<div class='benefit-card'><h5>Menos errores</h5><p>Reduce fallas de carga, medicacion y seguimiento con informacion mas clara y centralizada.</p></div>",
        "<div class='benefit-card'><h5>Mas control</h5><p>Coordina visitas, fichadas, urgencias, personal y documentacion desde un solo lugar.</p></div>",
        "<div class='benefit-card'><h5>Mas respaldo</h5><p>Deja cada accion registrada con firmas, auditoria y PDFs listos para presentar.</p></div>",
        "<div class='benefit-card'><h5>Mas escalable</h5><p>Sirve para profesionales independientes, empresas, coordinacion y redes de atencion.</p></div>",
        "</div>",
        "</div>",
        "<div class='segment-grid'>",
        "<div class='segment-card'><h4>Empresas de salud</h4><p>Coordina pacientes, personal, visitas, auditorias, alertas y documentacion sin depender de planillas sueltas.</p></div>",
        "<div class='segment-card'><h4>Profesionales de salud</h4><p>Registran atencion, signos, estudios e indicaciones desde el celular, con menos pasos y mejor respaldo.</p></div>",
        "<div class='segment-card'><h4>Coordinacion y administracion</h4><p>Visualizan agenda, carga operativa, equipo, RRHH y auditoria para tomar decisiones rapidas.</p></div>",
        "<div class='segment-card'><h4>Ambulancias y emergencias</h4><p>Dejan trazado el evento, el triage, el traslado y la atencion realizada dentro del mismo sistema.</p></div>",
        "</div>",
        "<div class='closing-banner'>",
        "<div class='closing-panel'><h3>Una presentacion fuerte para vender mejor</h3><p>Mostra una plataforma moderna, usable en celular y PC, con enfoque clinico, operativo y legal. Ideal para demos comerciales, reuniones con prestadores y propuestas para empresas de salud.</p></div>",
        "<div class='closing-panel'><h3>Listo para demo</h3><p>Podes presentar modulos, flujos por rol, documentos descargables y una experiencia real de trabajo en domicilio desde la primera reunion comercial.</p></div>",
        "</div>",
        "<div class='contact-section-pro'>",
        "<h3 style='color: white; margin: 0 0 10px; font-size: 2.2rem; font-weight: 900; letter-spacing: -1px;'>Necesitas soporte o implementacion?</h3>",
        "<p style='color: #cbd5e1; margin: 0 0 12px; font-size: 1.15rem;'>Comunicate directamente con nuestro equipo de especialistas.</p>",
        "<div class='contact-grid-pro'>",
        "<div class='contact-profile-pro'>",
        "<h4 class='p-name'>Enzo N. Girardi</h4>",
        "<p class='p-role'>Desarrollo y Soporte Tecnico</p>",
        "<div class='btn-flex-pro'>",
        "<a href='https://wa.me/5493584302024' target='_blank' class='btn-link-pro wpp-pro'>WhatsApp</a>",
        "<a href='mailto:enzogirardi84@gmail.com' class='btn-link-pro mail-pro'>Email</a>",
        "</div>",
        "</div>",
        "<div class='contact-profile-pro'>",
        "<h4 class='p-name'>Dario Lanfranco</h4>",
        "<p class='p-role'>Implementacion y Contratos</p>",
        "<div class='btn-flex-pro'>",
        "<a href='https://wa.me/5493584201263' target='_blank' class='btn-link-pro wpp-pro'>WhatsApp</a>",
        "<a href='mailto:dariolanfrancoruffener@gmail.com' class='btn-link-pro mail-pro'>Email</a>",
        "</div>",
        "</div>",
        "</div>",
        "</div>",
        "</div>",
    ]
    st.markdown("".join(html_lines), unsafe_allow_html=True)
    folleto_path = obtener_folleto_landing()
    if folleto_path:
        with folleto_path.open("rb") as brochure_file:
            st.download_button(
                "📥 Descargar presentacion comercial (PDF)",
                data=brochure_file.read(),
                file_name=folleto_path.name,
                mime="application/pdf",
                key="download_landing_brochure_pdf",
                use_container_width=False,
            )
    if st.button("🚀 INGRESAR AL SISTEMA", key="btn_ingresar_main"):
        st.session_state.entered_app = True
        st.rerun()
    st.stop()

render_login()
check_inactividad()

user = st.session_state.get("u_actual")
if not user:
    st.stop()

mi_empresa = user["empresa"]
rol = user["rol"]
logo_sidebar_path = Path(__file__).resolve().parent / "assets" / "logo_medicare_pro.jpeg"
logo_sidebar_b64 = base64.b64encode(logo_sidebar_path.read_bytes()).decode() if logo_sidebar_path.exists() else ""

if st.session_state.get("_modo_offline"):
    st.info("Modo local activo. Los cambios se guardan en este equipo hasta configurar Supabase correctamente.")

with st.sidebar:
    if st.button("Volver a la Publicidad", use_container_width=True):
        st.session_state.entered_app = False
        st.rerun()
    st.divider()

    st.markdown(
        f"""
        <div style="text-align:center; padding: 6px 0 16px;">
            <img src="data:image/jpeg;base64,{logo_sidebar_b64}"
                 style="width:132px; border-radius:22px; background:#ffffff; padding:12px; box-shadow:0 16px 34px rgba(2,6,23,0.28);" />
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.header(mi_empresa)
    st.write(f"**{user['nombre']}** ({rol})")
    alcance = (
        "Acceso de gestion y control total"
        if rol in ["SuperAdmin", "Coordinador"]
        else "Acceso asistencial limitado al registro clinico del paciente"
    )
    st.caption(alcance)
    st.divider()

    menu = [
        "Visitas y Agenda",
        "Clinica",
        "Pediatria",
        "Evolucion",
        "Estudios",
        "Materiales",
        "Recetas",
        "Balance",
        "Emergencias y Ambulancia",
        "Escalas Clinicas",
        "Historial",
        "PDF",
        "Telemedicina",
    ]

    if rol in ["SuperAdmin", "Coordinador"]:
        menu = [
            "Visitas y Agenda",
            "Dashboard",
            "Admision",
            "Clinica",
            "Pediatria",
            "Evolucion",
            "Estudios",
            "Materiales",
            "Recetas",
            "Balance",
            "Inventario",
            "Caja",
            "Emergencias y Ambulancia",
            "Red de Profesionales",
            "Escalas Clinicas",
            "Historial",
            "PDF",
            "Telemedicina",
            "Cierre Diario",
            "Mi Equipo",
            "Asistencia en Vivo",
            "RRHH y Fichajes",
            "Auditoria",
            "Auditoria Legal",
        ]
    elif rol == "Administrativo":
        menu = [
            "Dashboard",
            "Admision",
            "Inventario",
            "Caja",
            "Red de Profesionales",
            "Cierre Diario",
            "Mi Equipo",
            "Asistencia en Vivo",
            "RRHH y Fichajes",
            "Auditoria",
            "Auditoria Legal",
        ]
    menu = [modulo for modulo in menu if tiene_permiso(rol, VIEW_ROLE_RULES.get(modulo))]
    st.markdown(
        """
        <div class="mc-sidebar-section">
            <div class="mc-sidebar-kicker">Pacientes</div>
            <div class="mc-sidebar-title">Buscador y seleccion</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    buscar = st.text_input("Buscar Paciente", placeholder="Nombre, DNI o palabra clave")
    ver_altas = st.checkbox("Mostrar Pacientes de Alta") if rol in ["SuperAdmin", "Coordinador"] else False

    pacientes_visibles = []
    for p in st.session_state.get("pacientes_db", []):
        det = st.session_state.get("detalles_pacientes_db", {}).get(p, {})
        if rol != "SuperAdmin" and det.get("empresa") != mi_empresa:
            continue
        estado = det.get("estado", "Activo")
        if estado == "Activo" or ver_altas:
            display_name = _compact_patient_label(p, estado)
            pacientes_visibles.append((p, display_name, det.get("dni", ""), det.get("obra_social", ""), estado))

    pacientes_visibles.sort(key=lambda x: x[1].lower())
    p_f = [pv for pv in pacientes_visibles if buscar.lower() in pv[1].lower()]
    limite_pacientes = 80
    if not buscar and len(p_f) > limite_pacientes:
        st.caption(f"Mostrando los primeros {limite_pacientes} pacientes. Escribi para filtrar y ahorrar memoria.")
        p_f = p_f[:limite_pacientes]

    if not p_f and buscar:
        st.caption("No hay pacientes que coincidan con la busqueda.")
    elif p_f:
        st.caption(f"{len(p_f)} paciente(s) visibles")

    paciente_actual = st.session_state.get("paciente_actual")
    opciones_ids = [item[0] for item in p_f]
    index_actual = opciones_ids.index(paciente_actual) if paciente_actual in opciones_ids else 0
    paciente_sel_tuple = (
        st.selectbox(
            "Seleccionar Paciente",
            p_f,
            index=index_actual,
            format_func=lambda x: x[1],
            key="paciente_actual_select",
        )
        if p_f
        else None
    )
    paciente_sel = paciente_sel_tuple[0] if paciente_sel_tuple else None
    if paciente_sel:
        st.session_state["paciente_actual"] = paciente_sel
        det_sidebar = st.session_state["detalles_pacientes_db"].get(paciente_sel, {})
        st.markdown(_sidebar_patient_card(paciente_sel, det_sidebar), unsafe_allow_html=True)

    if paciente_sel:
        alertas = obtener_alertas_clinicas(st.session_state, paciente_sel)
        if alertas:
            colores = {
                "critica": ("#7f1d1d", "#fecaca", "#ef4444"),
                "alta": ("#78350f", "#fde68a", "#f59e0b"),
                "media": ("#172554", "#bfdbfe", "#38bdf8"),
            }
            bloques = []
            for alerta in alertas:
                fondo, texto, borde = colores.get(alerta["nivel"], colores["media"])
                bloques.append(
                    f"<div class='mc-sidebar-alert-card' style='background:{fondo}; border-color:{borde};'>"
                    f"<div class='mc-sidebar-alert-title' style='color:{texto};'>{escape(alerta['titulo'])}</div>"
                    f"<div class='mc-sidebar-alert-body' style='color:{texto};'>{escape(alerta['detalle']).replace(chr(10), '<br>')}</div>"
                    "</div>"
                )
            st.markdown(
                "<div class='mc-sidebar-alert-shell'>"
                "<div class='mc-sidebar-title'>Alertas clinicas</div>"
                + "".join(bloques)
                + "</div>",
                unsafe_allow_html=True,
            )
    if st.button("Cerrar Sesion", use_container_width=True):
        limpiar_sesion_app()
        st.rerun()

vista_actual = resolve_current_view(menu)
vista_actual = render_module_nav(menu, vista_actual)

if paciente_sel:
    det_actual = st.session_state["detalles_pacientes_db"].get(paciente_sel, {})
    st.markdown(
        f"""
        <div class="mc-callout">
            <strong>Paciente activo:</strong> {escape(paciente_sel)}<br>
            Empresa: {escape(det_actual.get('empresa', mi_empresa))} | DNI: {escape(det_actual.get('dni', 'S/D'))} | Estado: {escape(det_actual.get('estado', 'Activo'))}
        </div>
        """,
        unsafe_allow_html=True,
    )

render_current_view(vista_actual, paciente_sel, mi_empresa, user, rol)
