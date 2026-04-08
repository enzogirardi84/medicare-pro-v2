import base64
import os
import sys
from html import escape
from importlib import import_module
from pathlib import Path

import streamlit as st

from core.auth import check_inactividad, render_login
from core.utils import cargar_texto_asset, inicializar_db_state

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
    "Enfermeria": ("views.enfermeria", "render_enfermeria"),
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
    "Enfermeria": "🩹 Enfermeria",
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


def render_current_view(tab_name, paciente_sel, mi_empresa, user, rol):
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
        render_fn(paciente_sel, user)
    elif tab_name == "Estudios":
        render_fn(paciente_sel, user)
    elif tab_name == "Materiales":
        render_fn(paciente_sel, mi_empresa, user)
    elif tab_name == "Recetas":
        render_fn(paciente_sel, mi_empresa, user)
    elif tab_name == "Balance":
        render_fn(paciente_sel, user)
    elif tab_name == "Inventario":
        render_fn(mi_empresa)
    elif tab_name == "Caja":
        render_fn(paciente_sel, mi_empresa, user, rol)
    elif tab_name == "Emergencias y Ambulancia":
        render_fn(paciente_sel, mi_empresa, user)
    elif tab_name == "Enfermeria":
        render_fn(paciente_sel, mi_empresa, user)
    elif tab_name == "Escalas Clinicas":
        render_fn(paciente_sel, user)
    elif tab_name == "Historial":
        render_fn(paciente_sel)
    elif tab_name == "PDF":
        render_fn(paciente_sel, mi_empresa, user)
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
        </style>
        """,
        unsafe_allow_html=True,
    )

    html_lines = [
        "<style>",
        "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap');",
        ".landing-page { font-family: 'Inter', sans-serif; color: #f8fafc; display: flex; flex-direction: column; align-items: center; padding: 58px 20px 40px; }",
        ".logo-shell { background: rgba(255,255,255,0.98); padding: 16px 18px; border-radius: 26px; box-shadow: 0 12px 34px rgba(14,165,233,0.18); margin-bottom: 26px; }",
        ".title { font-size: clamp(2.5rem, 6vw, 4rem); font-weight: 900; line-height: 1.1; margin: 0 0 15px; text-align: center; letter-spacing: -1px; }",
        ".title-glow { background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }",
        ".subtitle { font-size: 1.18rem; color: #94a3b8; font-weight: 400; margin: 0 0 58px; max-width: 760px; text-align: center; line-height: 1.65; }",
        ".grid-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 28px; max-width: 1220px; width: 100%; margin-bottom: 72px; }",
        ".glass-card-pro { background: linear-gradient(145deg, rgba(24, 36, 61, 0.52) 0%, rgba(15, 23, 42, 0.94) 100%); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.07); border-radius: 28px; padding: 40px 30px; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); text-align: left; box-shadow: 0 10px 30px rgba(0,0,0,0.22); min-height: 238px; }",
        ".glass-card-pro:hover { transform: translateY(-8px); border-color: rgba(56, 189, 248, 0.45); box-shadow: 0 20px 40px rgba(0,0,0,0.35), 0 0 25px rgba(56,189,248,0.12); }",
        ".icon-box-pro { font-size: 2.35rem; margin-bottom: 22px; background: linear-gradient(135deg, rgba(56,189,248,0.14), rgba(14,165,233,0.05)); width: 82px; height: 82px; display: flex; align-items: center; justify-content: center; border-radius: 22px; border: 1px solid rgba(56,189,248,0.23); }",
        ".card-title-pro { font-size: 1.38rem; font-weight: 800; margin-bottom: 14px; color: #ffffff; letter-spacing: -0.5px; }",
        ".card-text-pro { color: #cbd5e1; font-size: 0.98rem; line-height: 1.7; margin: 0; font-weight: 400; }",
        ".contact-section-pro { max-width: 1040px; width: 100%; text-align: center; background: linear-gradient(145deg, rgba(13, 21, 44, 0.86), rgba(2, 6, 23, 0.98)); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 38px; padding: 54px 34px; box-shadow: 0 18px 44px rgba(0,0,0,0.28); }",
        ".contact-grid-pro { display: flex; flex-wrap: wrap; justify-content: center; gap: 36px; margin-top: 34px; }",
        ".contact-profile-pro { flex: 1; min-width: 280px; max-width: 420px; background: rgba(24, 36, 61, 0.48); padding: 34px 24px; border-radius: 24px; border: 1px solid rgba(255, 255, 255, 0.05); transition: 0.3s; box-shadow: inset 0 0 0 1px rgba(56,189,248,0.06); }",
        ".contact-profile-pro:hover { background: rgba(30, 41, 59, 0.58); border-color: rgba(56, 189, 248, 0.3); }",
        ".p-name { font-size: 1.46rem; font-weight: 700; color: #ffffff; margin: 0 0 8px; }",
        ".p-role { font-size: 0.82rem; color: #38bdf8; text-transform: uppercase; letter-spacing: 1.6px; font-weight: 800; margin: 0 0 28px; line-height: 1.45; }",
        ".btn-flex-pro { display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; }",
        ".btn-link-pro { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 14px 22px; border-radius: 14px; text-decoration: none; font-weight: 700; font-size: 0.95rem; transition: all 0.3s; min-width: 166px; color: white !important; }",
        ".wpp-pro { background: linear-gradient(135deg, #22c55e, #16a34a); box-shadow: 0 4px 15px rgba(34,197,94,0.28); }",
        ".wpp-pro:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(34,197,94,0.42); filter: brightness(1.08); }",
        ".mail-pro { background: linear-gradient(135deg, #3b82f6, #2563eb); box-shadow: 0 4px 15px rgba(59,130,246,0.28); }",
        ".mail-pro:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(59,130,246,0.42); filter: brightness(1.08); }",
        "@media (max-width: 768px) { .landing-page { padding: 42px 18px 24px; } .grid-cards { gap: 20px; margin-bottom: 48px; } .glass-card-pro { padding: 28px 22px; min-height: auto; } .contact-section-pro { padding: 36px 18px; border-radius: 26px; } .contact-grid-pro { gap: 20px; } }",
        "</style>",
        "<div class='landing-page'>",
        f"<div class='logo-shell'>{logo_html}</div>",
        "<h1 class='title'>Gestión Domiciliaria <br><span class='title-glow'>Inteligente</span></h1>",
        "<p class='subtitle'>Módulos avanzados y diseño intuitivo para llevar el control de tu clínica al máximo nivel, optimizando tiempo y recursos.</p>",
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
        "<div class='contact-section-pro'>",
        "<h3 style='color: white; margin: 0 0 10px; font-size: 2.2rem; font-weight: 900; letter-spacing: -1px;'>¿Necesitas soporte o implementación?</h3>",
        "<p style='color: #cbd5e1; margin: 0 0 12px; font-size: 1.15rem;'>Comunícate directamente con nuestro equipo de especialistas.</p>",
        "<div class='contact-grid-pro'>",
        "<div class='contact-profile-pro'>",
        "<h4 class='p-name'>Enzo N. Girardi</h4>",
        "<p class='p-role'>Desarrollo y Soporte Técnico</p>",
        "<div class='btn-flex-pro'>",
        "<a href='https://wa.me/5493584302024' target='_blank' class='btn-link-pro wpp-pro'>💬 WhatsApp</a>",
        "<a href='mailto:enzogirardi84@gmail.com' class='btn-link-pro mail-pro'>✉️ Email</a>",
        "</div>",
        "</div>",
        "<div class='contact-profile-pro'>",
        "<h4 class='p-name'>Darío Lanfranco</h4>",
        "<p class='p-role'>Implementación y Contratos</p>",
        "<div class='btn-flex-pro'>",
        "<a href='https://wa.me/5493584201263' target='_blank' class='btn-link-pro wpp-pro'>💬 WhatsApp</a>",
        "<a href='mailto:dariolanfrancoruffener@gmail.com' class='btn-link-pro mail-pro'>✉️ Email</a>",
        "</div>",
        "</div>",
        "</div>",
        "</div>",
        "</div>",
    ]
    st.markdown("".join(html_lines), unsafe_allow_html=True)
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
    st.divider()

    menu = [
        "Visitas y Agenda",
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
        "Enfermeria",
        "Escalas Clinicas",
        "Historial",
        "PDF",
        "Telemedicina",
    ]

    if rol in ["SuperAdmin", "Coordinador"]:
        menu.insert(1, "Dashboard")
        menu.extend(["Cierre Diario", "Mi Equipo", "Asistencia en Vivo", "RRHH y Fichajes", "Auditoria", "Auditoria Legal"])
    buscar = st.text_input("Buscar Paciente")
    ver_altas = st.checkbox("Mostrar Pacientes de Alta") if rol in ["SuperAdmin", "Coordinador"] else False

    pacientes_visibles = []
    for p in st.session_state.get("pacientes_db", []):
        det = st.session_state.get("detalles_pacientes_db", {}).get(p, {})
        if rol != "SuperAdmin" and det.get("empresa") != mi_empresa:
            continue
        estado = det.get("estado", "Activo")
        if estado == "Activo" or ver_altas:
            display_name = f"{p} [ALTA]" if estado == "De Alta" else p
            pacientes_visibles.append((p, display_name))

    pacientes_visibles.sort(key=lambda x: x[1].lower())
    p_f = [pv for pv in pacientes_visibles if buscar.lower() in pv[1].lower()]
    limite_pacientes = 80
    if not buscar and len(p_f) > limite_pacientes:
        st.caption(f"Mostrando los primeros {limite_pacientes} pacientes. Escribi para filtrar y ahorrar memoria.")
        p_f = p_f[:limite_pacientes]

    if not p_f and buscar:
        st.caption("No hay pacientes que coincidan con la busqueda.")

    paciente_actual = st.session_state.get("paciente_actual")
    opciones_ids = [item[0] for item in p_f]
    index_actual = opciones_ids.index(paciente_actual) if paciente_actual in opciones_ids else 0
    paciente_sel_tuple = st.selectbox("Seleccionar Paciente", p_f, index=index_actual, format_func=lambda x: x[1], key="paciente_actual_select") if p_f else None
    paciente_sel = paciente_sel_tuple[0] if paciente_sel_tuple else None
    if paciente_sel:
        st.session_state["paciente_actual"] = paciente_sel

    if paciente_sel:
        det_pac = st.session_state["detalles_pacientes_db"].get(paciente_sel, {})
        alergias_pac = det_pac.get("alergias", "").strip()
        patologias_pac = det_pac.get("patologias", "").strip()
        if alergias_pac or patologias_pac:
            alergias_html = escape(alergias_pac).replace("\n", "<br>") if alergias_pac else ""
            patologias_html = escape(patologias_pac).replace("\n", "<br>") if patologias_pac else ""
            alerta_html = f"""<div style='background-color: #450a0a; border: 2px solid #ef4444; border-radius: 10px; padding: 12px; margin-top: 15px; margin-bottom: 15px;'>
            <h4 style='color: #f87171; margin-top: 0; margin-bottom: 8px; text-transform: uppercase; font-weight: 900;'>ALERTA CLINICA</h4>
            {f"<p style='color: #fca5a5; margin: 0 0 6px 0; font-size: 0.9rem;'><b>Alergias:</b><br>{alergias_html}</p>" if alergias_pac else ""}
            {f"<p style='color: #fca5a5; margin: 0; font-size: 0.9rem;'><b>Patologias / Riesgos:</b><br>{patologias_html}</p>" if patologias_pac else ""}
            </div>"""
            st.markdown(alerta_html, unsafe_allow_html=True)
    if st.button("Cerrar Sesion", use_container_width=True):
        limpiar_sesion_app()
        st.rerun()

vista_actual = st.radio(
    "Modulo",
    menu,
    key="modulo_actual",
    horizontal=True,
    label_visibility="collapsed",
    format_func=lambda x: VIEW_LABELS.get(x, x),
)

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
