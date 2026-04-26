import base64
import sys
import time
from html import escape
from importlib import import_module
from pathlib import Path
from urllib.parse import quote_plus

import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# BOOTSTRAP DE RUTAS
# ============================================================

def _insert_repo_root_on_path() -> Path:
    """
    Streamlit Cloud puede ejecutar main.py dentro de una subcarpeta.
    Subimos directorios hasta encontrar core/ y lo agregamos a sys.path.
    """
    here = Path(__file__).resolve().parent
    cur: Path = here
    root = here

    for _ in range(5):
        if (cur / "core").is_dir():
            root = cur
            break
        parent = cur.parent
        if parent == cur:
            break
        cur = parent

    rs = str(root)
    if rs not in sys.path:
        sys.path.insert(0, rs)

    hs = str(here)
    if hs != rs and hs not in sys.path:
        sys.path.insert(0, hs)

    return root


REPO_ROOT = _insert_repo_root_on_path()


# ============================================================
# IMPORTS BASE
# ============================================================

from core.landing_runner import ensure_entered_app_default, render_publicidad_y_detener
from core.seo_streamlit import (
    PAGE_TITLE_PUBLIC,
    inyectar_head_seo,
    inyectar_redirect_apex_si_configurado,
)

from core.feature_flags import ALERTAS_APP_PACIENTE_VISIBLE
from core.view_registry import build_view_maps
from core.user_feedback import render_carga_modulo_fallo, render_modulo_fallo_ui

from core.app_logging import configurar_logging_basico, log_event
from core.perf_metrics import record_perf, summarize_perf
from core.ui_professional import apply_professional_theme

from core.nav_helpers import MC_FILTRO_TODAS  # noqa: F401

from core.sidebar_components import (
    render_sidebar_contexto_clinico as _render_sidebar_contexto_clinico,
    render_sidebar_pacientes_y_alertas as _render_sidebar_pacientes_y_alertas_fn,
)

from core.view_dispatch import (
    render_current_view as _render_current_view_dispatch,
    resolve_current_view,
    resolve_menu_for_role as _resolve_menu_for_role_dispatch,
)


# ============================================================
# CONFIGURACIÓN INICIAL
# ============================================================

APP_BUILD_TAG = "Build 2026-04-24 main mejorado: nav grid + CSS estable + fallbacks"

st.set_page_config(
    page_title=PAGE_TITLE_PUBLIC,
    layout="wide",
    initial_sidebar_state="expanded",
)

configurar_logging_basico()


# ============================================================
# CSS GLOBAL MÁS SEGURO
# ============================================================

def aplicar_css_base():
    """
    CSS general.
    Evita depender de selectores frágiles con :has() y nth-child()
    para la navegación principal.
    """
    st.markdown(
        """
        <style>
            /* =============================
               BASE VISUAL GENERAL
               ============================= */

            html, body, [data-testid="stAppViewContainer"] {
                background: #0f172a;
            }

            div[data-testid="stButton"] > button {
                border-radius: 18px !important;
                border: 1px solid rgba(14, 165, 233, 0.28) !important;
                background: rgba(15, 23, 42, 0.55) !important;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.14) !important;
                transition: all 0.18s ease !important;
                padding: 0.5rem 1rem !important;
                color: #ffffff !important;
            }

            div[data-testid="stButton"] > button:hover {
                transform: translateY(-1px) !important;
                border-color: #0ea5e9 !important;
                box-shadow: 0 6px 15px rgba(14, 165, 233, 0.20) !important;
                color: white !important;
            }

            div[data-testid="stButton"] > button p,
            div[data-testid="stButton"] > button div,
            div[data-testid="stButton"] > button span {
                color: #ffffff !important;
                font-weight: 600 !important;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] {
                border-radius: 22px !important;
                border: 1px solid rgba(255, 255, 255, 0.06) !important;
                box-shadow: 0 10px 28px rgba(0, 0, 0, 0.18) !important;
                background-color: rgba(17, 24, 39, 0.90) !important;
                overflow: hidden !important;
            }

            div[data-testid="stTextInput"] input,
            div[data-baseweb="select"] > div {
                border-radius: 14px !important;
                border: 1px solid rgba(255, 255, 255, 0.10) !important;
                background-color: rgba(255, 255, 255, 0.035) !important;
            }

            div[data-testid="stMetric"] {
                background-color: rgba(255, 255, 255, 0.025) !important;
                border-radius: 16px !important;
                padding: 10px !important;
                border: 1px solid rgba(255, 255, 255, 0.055) !important;
            }

            [data-testid="stSidebar"] [data-testid="stMetricValue"] {
                font-size: 1.2rem !important;
            }

            [data-testid="stSidebar"] [data-testid="stMetricLabel"] {
                font-size: 0.8rem !important;
            }

            [data-testid="stSidebar"] div[data-testid="column"] {
                padding: 0 !important;
            }


            /* =============================
               NAVEGACIÓN DE MÓDULOS
               Grilla propia, sin st.columns
               ============================= */

            .mc-module-nav-wrap {
                width: 100%;
                margin: 8px 0 26px 0;
            }

            .mc-module-nav-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(150px, 150px));
                gap: 10px;
                justify-content: start;
                align-items: stretch;
            }

            .mc-module-card {
                height: 58px;
                padding: 0 13px;
                display: flex;
                align-items: center;
                justify-content: flex-start;
                gap: 8px;

                border-radius: 16px;
                border: 1px solid rgba(148, 163, 184, 0.32);
                background: rgba(15, 23, 42, 0.88);

                color: #ffffff !important;
                text-decoration: none !important;

                box-shadow: 0 4px 10px rgba(0,0,0,0.18);
                transition: all 0.16s ease;
                overflow: hidden;
            }

            .mc-module-card:hover {
                border-color: rgba(56, 189, 248, 0.85);
                background: rgba(30, 41, 59, 0.98);
                transform: translateY(-1px);
                box-shadow: 0 8px 20px rgba(14,165,233,0.14);
            }

            .mc-module-card.active {
                border-color: #38bdf8;
                background: linear-gradient(
                    135deg,
                    rgba(14,165,233,0.30),
                    rgba(15,23,42,0.95)
                );
                box-shadow:
                    0 0 0 1px rgba(56,189,248,0.35),
                    0 8px 22px rgba(14,165,233,0.12);
            }

            .mc-module-icon {
                font-size: 18px;
                line-height: 1;
                flex: 0 0 auto;
            }

            .mc-module-text {
                font-size: 13px;
                font-weight: 650;
                line-height: 1.2;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                min-width: 0;
                color: #ffffff !important;
            }

            .mc-module-empty {
                color: rgba(226,232,240,0.75);
                font-size: 0.9rem;
                padding: 8px 0;
            }


            /* =============================
               BOTÓN FLOTANTE PACIENTES
               ============================= */

            #btn-flotante-pacientes {
                position: fixed;
                bottom: 40px;
                left: 0;
                z-index: 999999;
                background: rgba(14, 165, 233, 0.95) !important;
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                color: #ffffff !important;
                padding: 12px 18px 12px 12px;
                border-radius: 0 24px 24px 0;
                font-weight: 700 !important;
                font-size: 15px !important;
                box-shadow: 2px 4px 12px rgba(0,0,0,0.5);
                cursor: pointer;
                border: 1px solid rgba(255,255,255,0.4);
                border-left: none;
                display: none;
            }


            /* =============================
               MÓVIL
               ============================= */

            @media (max-width: 768px) {
                .mc-module-nav-grid {
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    gap: 8px;
                }

                .mc-module-card {
                    height: 68px;
                    padding: 7px 5px;
                    flex-direction: column;
                    justify-content: center;
                    text-align: center;
                    gap: 5px;
                    border-radius: 15px;
                }

                .mc-module-icon {
                    font-size: 18px;
                }

                .mc-module-text {
                    font-size: 10.5px;
                    max-width: 100%;
                }

                #btn-flotante-pacientes {
                    display: block;
                }
            }

            @media (min-width: 1200px) {
                .mc-module-nav-grid {
                    grid-template-columns: repeat(auto-fill, minmax(158px, 158px));
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


aplicar_css_base()


# ============================================================
# SEO / LANDING
# ============================================================

inyectar_redirect_apex_si_configurado()

if not st.session_state.get("_mc_seo_head_inyectado"):
    inyectar_head_seo()
    st.session_state["_mc_seo_head_inyectado"] = True

ensure_entered_app_default()

if not st.session_state.get("entered_app"):
    render_publicidad_y_detener()


# ============================================================
# IMPORTS DINÁMICOS / FALLBACKS
# ============================================================

_core_auth = import_module("core.auth")
check_inactividad = _core_auth.check_inactividad
render_login = _core_auth.render_login
verificar_clinica_sesion_activa = getattr(
    _core_auth,
    "verificar_clinica_sesion_activa",
    lambda: None,
)

core_utils = import_module("core.utils")

_core_database = import_module("core.database")
obtener_estado_guardado = getattr(_core_database, "obtener_estado_guardado", lambda: {})
completar_claves_db_session = getattr(_core_database, "completar_claves_db_session", lambda: None)
procesar_guardado_pendiente = getattr(_core_database, "procesar_guardado_pendiente", lambda: False)

guardar_datos = getattr(_core_database, "guardar_datos", None)

_vr = import_module("core.view_roles")
MODULO_ROLES_PERMITIDOS = _vr.MODULO_ROLES_PERMITIDOS
tiene_acceso_vista = _vr.tiene_acceso_vista

cargar_texto_asset = core_utils.cargar_texto_asset

es_control_total = getattr(
    core_utils,
    "es_control_total",
    lambda rol, usuario_actual=None: str(rol or "").strip().lower()
    in {"superadmin", "admin", "coordinador", "administrativo"},
)

inicializar_db_state = core_utils.inicializar_db_state

mapa_detalles_pacientes = getattr(
    core_utils,
    "mapa_detalles_pacientes",
    lambda ss: ss.get("detalles_pacientes_db")
    if isinstance(ss.get("detalles_pacientes_db"), dict)
    else {},
)

obtener_alertas_clinicas = core_utils.obtener_alertas_clinicas

modo_celular_viejo_activo = getattr(
    core_utils,
    "modo_celular_viejo_activo",
    lambda session_state=None: False,
)

obtener_pacientes_visibles = getattr(
    core_utils,
    "obtener_pacientes_visibles",
    lambda session_state, mi_empresa, rol, incluir_altas=False, busqueda="": [],
)

descripcion_acceso_rol = getattr(
    core_utils,
    "descripcion_acceso_rol",
    lambda rol: (
        "Acceso de gestion y control total"
        if str(rol or "").strip().lower()
        in {"superadmin", "admin", "coordinador", "administrativo"}
        else "Acceso asistencial limitado al registro clinico del paciente"
    ),
)

obtener_modulos_permitidos = getattr(core_utils, "obtener_modulos_permitidos", None)

valor_por_modo_liviano = getattr(
    core_utils,
    "valor_por_modo_liviano",
    lambda normal, liviano, session_state=None: normal,
)

headers_sugieren_equipo_liviano = getattr(
    core_utils,
    "headers_sugieren_equipo_liviano",
    lambda: False,
)

try:
    ui_liv = import_module("core.ui_liviano")
except Exception:
    class _UILivFallback:
        @staticmethod
        def user_agent_desde_contexto():
            return ""

        @staticmethod
        def user_agent_es_telefono_movil_probable(ua):
            return False

        @staticmethod
        def user_agent_es_tablet_probable(ua):
            return False

    ui_liv = _UILivFallback()


def _guardar_datos_seguro(spinner=True):
    """
    Evita que el botón Guardar rompa la app si guardar_datos
    no existe o cambió de lugar.
    """
    global guardar_datos

    if callable(guardar_datos):
        try:
            return guardar_datos(spinner=spinner)
        except TypeError:
            return guardar_datos()

    try:
        from core.database import guardar_datos as _gd
        guardar_datos = _gd
        try:
            return guardar_datos(spinner=spinner)
        except TypeError:
            return guardar_datos()
    except Exception as exc:
        log_event("main_guardar", f"guardar_datos_no_disponible:{type(exc).__name__}:{exc}")
        st.warning("No se encontró la función de guardado. Revisá core.database.guardar_datos.")
        return False


# ============================================================
# VIEW MAPS
# ============================================================

VIEW_CONFIG, VIEW_NAV_LABELS = build_view_maps(
    alertas_app_visible=ALERTAS_APP_PACIENTE_VISIBLE
)


# ============================================================
# SESIÓN / LIMPIEZA
# ============================================================

def limpiar_sesion_app():
    from core.database import vaciar_datos_app_en_sesion
    from core.session_auth_cleanup import limpiar_estado_sesion_login_efimero

    claves = [
        "logeado",
        "u_actual",
        "ultima_actividad",
        "modulo_actual",
        "modulo_anterior",
        "paciente_actual",
        "entered_app",
    ]

    for clave in claves:
        st.session_state.pop(clave, None)

    limpiar_estado_sesion_login_efimero()
    vaciar_datos_app_en_sesion()

    for clave in [
        "_mc_onboarding_oculto",
        "_db_monolito_sesion",
        "_mc_aviso_payload_grande",
        "mc_nav_filtro_cat",
        "_mc_sidebar_logo_b64",
        "_mc_anticolapso_secret_cached",
        "_mc_professional_theme_applied",
        "_mc_login_transition",
        "_mc_cache_headers_liviano",
        "_mc_cache_ua_contexto",
    ]:
        st.session_state.pop(clave, None)

    st.session_state["entered_app"] = False


# Eliminar overlay residual
st.session_state.pop("_mc_login_transition", None)

if "_db_bootstrapped" not in st.session_state:
    inicializar_db_state(None, precargar_usuario_admin_emergencia=False)
    st.session_state["_db_bootstrapped"] = True


# ============================================================
# LOGIN
# ============================================================

render_login()
verificar_clinica_sesion_activa()
check_inactividad()

user = st.session_state.get("u_actual")

if not isinstance(user, dict) or not user:
    st.stop()


# ============================================================
# TEMA PROFESIONAL POSLOGIN
# ============================================================

if not st.session_state.get("_mc_professional_theme_applied"):
    try:
        apply_professional_theme()
        st.session_state["_mc_professional_theme_applied"] = True
    except Exception as exc:
        log_event("ui_theme", f"Error aplicando tema: {exc}")


# ============================================================
# GUARDADOS PENDIENTES
# ============================================================

try:
    procesar_guardado_pendiente()
except Exception as exc:
    log_event(
        "main_rerun",
        f"procesar_guardado_pendiente_falla:{type(exc).__name__}:{exc}",
    )


# ============================================================
# NORMALIZAR USUARIO
# ============================================================

_user_base = dict(user)

_canon = core_utils.normalizar_usuario_sistema(dict(_user_base))
_merged = dict(_user_base)

for _k in ("rol", "perfil_profesional", "empresa", "nombre", "email", "pin"):
    if _k in _canon and _canon.get(_k) != _user_base.get(_k):
        _merged[_k] = _canon[_k]

_merged.setdefault("nombre", "Usuario sin nombre")
_merged.setdefault("empresa", "Clinica General")
_merged.setdefault("rol", "Operativo")

st.session_state["u_actual"] = _merged

user = st.session_state.get("u_actual")

if not isinstance(user, dict) or not user:
    st.stop()


# ============================================================
# IMPORTS PESADOS SOLO CON SESIÓN VÁLIDA
# ============================================================

_ac = import_module("core.anticolapso")
aplicar_politicas_anticolapso_ui = _ac.aplicar_politicas_anticolapso_ui
anticolapso_activo_fn = _ac.anticolapso_activo
limite_pacientes_sidebar = _ac.limite_pacientes_sidebar
render_estabilidad_anticolapso_sidebar = _ac.render_estabilidad_anticolapso_sidebar

_onb = import_module("core.onboarding")
render_panel_bienvenida = _onb.render_panel_bienvenida

_aa = import_module("core.alertas_app_paciente_ui")
render_banner_alertas_criticas_si_aplica = _aa.render_banner_alertas_criticas_si_aplica
render_sidebar_bloque_app_paciente = _aa.render_sidebar_bloque_app_paciente

_ns = import_module("core.notificaciones_superiores")
render_franja_avisos_operativos = _ns.render_franja_avisos_operativos
render_alerta_inventario_banda_superior = _ns.render_alerta_inventario_banda_superior

_rn = import_module("core.release_notes")
MC_APP_CHANGELOG = _rn.MC_APP_CHANGELOG

completar_claves_db_session()


# ============================================================
# CONTEXTO USUARIO
# ============================================================

mi_empresa = str(user.get("empresa", "Clinica General") or "Clinica General")
rol = str(user.get("rol", "Operativo") or "Operativo")


# ============================================================
# LOGO SIDEBAR CACHEADO
# ============================================================

_logo_ck = "_mc_sidebar_logo_b64"

if _logo_ck not in st.session_state:
    logo_sidebar_path = Path(__file__).resolve().parent / "assets" / "logo_medicare_pro.jpeg"
    try:
        st.session_state[_logo_ck] = (
            base64.b64encode(logo_sidebar_path.read_bytes()).decode()
            if logo_sidebar_path.exists()
            else ""
        )
    except OSError:
        st.session_state[_logo_ck] = ""

logo_sidebar_b64 = st.session_state[_logo_ck]


if st.session_state.get("_modo_offline"):
    st.info(
        "Modo local activo. Los cambios se guardan en este equipo "
        "hasta configurar Supabase correctamente."
    )


# ============================================================
# BOTÓN FLOTANTE PACIENTES
# ============================================================

st.markdown(
    """
    <div id="btn-flotante-pacientes">
        ☰ Pacientes
    </div>
    """,
    unsafe_allow_html=True,
)

components.html(
    """
    <script>
        const doc = window.parent.document;
        const btnPacientes = doc.getElementById('btn-flotante-pacientes');

        if (btnPacientes && !btnPacientes.dataset.mcBound) {
            btnPacientes.dataset.mcBound = "1";

            btnPacientes.addEventListener('click', function() {
                const sidebarBtn =
                    doc.querySelector('[data-testid="collapsedControl"]') ||
                    doc.querySelector('header button');

                if (sidebarBtn) {
                    sidebarBtn.click();
                } else {
                    console.log("No se encontro el menu lateral nativo de Streamlit");
                }
            });
        }
    </script>
    """,
    height=0,
    width=0,
)


# ============================================================
# HELPERS DE NAVEGACIÓN
# ============================================================

def resolve_menu_for_role(rol_actual, user_actual=None):
    return _resolve_menu_for_role_dispatch(
        rol_actual,
        user_actual,
        VIEW_CONFIG,
        obtener_modulos_permitidos,
    )


def render_current_view(tab_name, paciente_sel, mi_empresa, user, rol, menu_set=None):
    if menu_set is None:
        menu_set = frozenset(resolve_menu_for_role(rol, user))

    _render_current_view_dispatch(
        tab_name,
        paciente_sel,
        mi_empresa,
        user,
        rol,
        VIEW_CONFIG,
        menu_set,
    )


def _split_icon_label(label: str):
    """
    Si el label viene como '📋 Pacientes', separa icono y texto.
    Si no trae icono, usa un icono genérico.
    """
    label = str(label or "").strip()

    if not label:
        return "▣", ""

    partes = label.split(maxsplit=1)

    if len(partes) == 2:
        posible_icono, texto = partes
        if not posible_icono.replace("_", "").isalnum():
            return posible_icono, texto

    return "▣", label


def procesar_query_params_navegacion(menu_set):
    """
    Lee ?modulo= desde links HTML y actualiza session_state.
    Después limpia el query param para evitar bucles.
    """
    qp = getattr(st, "query_params", None)

    if qp is None:
        return

    try:
        raw_mod = qp.get("modulo")

        if raw_mod is None:
            return

        effective = str(raw_mod[0] if isinstance(raw_mod, list) else raw_mod).strip()

        if effective and effective in menu_set:
            actual = st.session_state.get("modulo_actual")

            if actual != effective:
                st.session_state["modulo_anterior"] = actual
                st.session_state["modulo_actual"] = effective

        try:
            del st.query_params["modulo"]
        except Exception:
            pass

        st.rerun()

    except Exception as exc:
        log_event("main_nav", f"query_params_nav_error:{type(exc).__name__}:{exc}")


def render_module_nav_grid(menu, vista_actual, menu_set=None):
    """
    Navegación principal via st.pills — evita recarga de página y pérdida de sesión.
    """
    if menu_set is None:
        menu_set = frozenset(menu)

    if not menu:
        st.info("No hay módulos disponibles.")
        return vista_actual

    pill_options = [m for m in menu if m in menu_set]

    if not pill_options:
        st.info("No hay módulos disponibles.")
        return vista_actual

    key_pills = "mc_nav_pills"

    # Sincronizar widget con el módulo actual (ej. navegación via sidebar o atajo)
    current_val = st.session_state.get(key_pills)
    if current_val not in pill_options:
        st.session_state[key_pills] = vista_actual if vista_actual in pill_options else pill_options[0]

    def _on_nav_change():
        selected = st.session_state.get(key_pills)
        if selected and selected != st.session_state.get("modulo_actual"):
            st.session_state["modulo_anterior"] = st.session_state.get("modulo_actual")
            st.session_state["modulo_actual"] = selected

    selected = st.pills(
        "",
        options=pill_options,
        format_func=lambda x: VIEW_NAV_LABELS.get(x, x),
        key=key_pills,
        label_visibility="collapsed",
        on_change=_on_nav_change,
    )

    return selected or vista_actual


# ============================================================
# DETECCIÓN MÓVIL SEGURA
# ============================================================

def _cliente_es_movil_probable():
    if st.session_state.get("mc_liviano_modo") == "on":
        return True

    try:
        if headers_sugieren_equipo_liviano():
            return True
    except Exception:
        pass

    try:
        ua = ui_liv.user_agent_desde_contexto()
        return (
            ui_liv.user_agent_es_telefono_movil_probable(ua)
            or ui_liv.user_agent_es_tablet_probable(ua)
        )
    except Exception:
        return False


def _cliente_es_tablet_probable():
    try:
        ua = ui_liv.user_agent_desde_contexto()
        return ui_liv.user_agent_es_tablet_probable(ua)
    except Exception:
        return False


def _render_mobile_patient_selector(mi_empresa, rol):
    """
    Selector alternativo de pacientes para móviles.
    No reemplaza al sidebar; solo ayuda cuando el sidebar molesta.
    """
    if not _cliente_es_movil_probable():
        return None

    es_tablet = _cliente_es_tablet_probable()

    with st.expander(
        "Selector de paciente",
        expanded=(st.session_state.get("paciente_actual") is None),
    ):
        st.caption("Buscá por nombre, DNI o empresa.")

        buscar = st.text_input(
            "Buscar paciente",
            placeholder="Nombre, DNI o palabra clave",
            key="mc_buscar_paciente_mobile",
        )

        p_f = obtener_pacientes_visibles(
            st.session_state,
            mi_empresa,
            rol,
            incluir_altas=False,
            busqueda=buscar,
        )

        limite = 25 if es_tablet else 15

        if not buscar and len(p_f) > limite:
            st.caption(f"Mostrando {limite} pacientes. Escribí para filtrar.")
            p_f = p_f[:limite]

        if not p_f:
            st.warning("No hay pacientes visibles.")
            return None

        opciones = [item[0] for item in p_f]
        display_map = {item[0]: item[1] for item in p_f}

        paciente_sel_mobile = st.selectbox(
            "Seleccionar paciente",
            opciones,
            format_func=lambda x: display_map.get(x, x),
            key="paciente_actual_select_mobile",
        )

        if paciente_sel_mobile and paciente_sel_mobile != st.session_state.get("paciente_actual"):
            st.session_state["paciente_actual"] = paciente_sel_mobile
            st.rerun()

        if paciente_sel_mobile:
            det = mapa_detalles_pacientes(st.session_state).get(paciente_sel_mobile, {})
            st.success(str(paciente_sel_mobile))
            st.caption(
                f"DNI: {det.get('dni', 'S/D')} | "
                f"OS: {det.get('obra_social', 'S/D')}"
            )

        return paciente_sel_mobile


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Guardar", use_container_width=True, key="sidebar_guardar"):
            _guardar_datos_seguro(spinner=True)

    with col2:
        if st.button("Abrir", use_container_width=True, key="sidebar_abrir"):
            from core.database import vaciar_datos_app_en_sesion
            from core.session_auth_cleanup import limpiar_estado_sesion_login_efimero

            st.session_state.entered_app = False
            st.session_state["logeado"] = False

            for _k in (
                "u_actual",
                "paciente_actual",
                "modulo_actual",
                "modulo_anterior",
                "ultima_actividad",
            ):
                st.session_state.pop(_k, None)

            limpiar_estado_sesion_login_efimero()
            vaciar_datos_app_en_sesion()
            st.rerun()

    st.divider()

    paciente_sel = _render_sidebar_pacientes_y_alertas_fn(
        mi_empresa,
        rol,
        obtener_pacientes_fn=obtener_pacientes_visibles,
        obtener_alertas_fn=obtener_alertas_clinicas,
        mapa_detalles_fn=mapa_detalles_pacientes,
        es_control_total_fn=es_control_total,
        valor_por_modo_liviano_fn=valor_por_modo_liviano,
        limite_pacientes_fn=limite_pacientes_sidebar,
    )


# ============================================================
# MENÚ Y NAVEGACIÓN
# ============================================================

menu = resolve_menu_for_role(rol, user)
menu_set = frozenset(menu)

# Navegación via grilla HTML: procesar ?modulo= desde links <a> sin st.columns
procesar_query_params_navegacion(menu_set)

vista_actual = resolve_current_view(menu, menu_set)

if not vista_actual:
    st.warning(
        "No hay módulos habilitados para este usuario. "
        "Revisá el rol asignado o la configuración de permisos."
    )
    st.stop()


# Selector alternativo en móvil
paciente_mobile = _render_mobile_patient_selector(mi_empresa, rol)

if paciente_mobile:
    paciente_sel = paciente_mobile


# Grilla de módulos estable
vista_actual = render_module_nav_grid(menu, vista_actual, menu_set)

if not vista_actual:
    st.warning("No se pudo resolver un módulo visible para este usuario.")
    st.stop()


# ============================================================
# CONTEXTO CLÍNICO / NOTIFICACIONES
# ============================================================

_render_sidebar_contexto_clinico(paciente_sel, vista_actual)

# Panel de bienvenida removido por pedido del usuario.
# render_panel_bienvenida(rol, menu, VIEW_NAV_LABELS)

render_banner_alertas_criticas_si_aplica(mi_empresa)
render_franja_avisos_operativos(mi_empresa)


# ============================================================
# TARJETA DE PACIENTE / ATAJO ANTERIOR
# ============================================================

modulo_anterior = st.session_state.get("modulo_anterior")
mostrar_atajo = (
    modulo_anterior
    and modulo_anterior in menu_set
    and modulo_anterior != vista_actual
)

if mostrar_atajo or paciente_sel:
    if mostrar_atajo and paciente_sel:
        col_nav, col_call = st.columns([1, 4])

        with col_nav:
            etiqueta_ant = VIEW_NAV_LABELS.get(modulo_anterior, modulo_anterior)

            if st.button(
                "← Anterior",
                help=f"Volver a: {etiqueta_ant}",
                use_container_width=True,
                key="mc_atajo_modulo_anterior",
            ):
                cur = vista_actual
                st.session_state["modulo_actual"] = modulo_anterior
                st.session_state["modulo_anterior"] = cur
                st.rerun()

        with col_call:
            det_actual = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})

            with st.container(border=True):
                st.write(f"**{escape(str(paciente_sel))}**")
                st.caption(
                    f"{escape(str(det_actual.get('empresa', mi_empresa)))}  ·  "
                    f"DNI {escape(str(det_actual.get('dni', 'S/D')))}  ·  "
                    f"{escape(str(det_actual.get('estado', 'Activo')))}"
                )

    elif mostrar_atajo:
        etiqueta_ant = VIEW_NAV_LABELS.get(modulo_anterior, modulo_anterior)

        if st.button(
            f"← Volver a {etiqueta_ant}",
            use_container_width=False,
            key="mc_atajo_modulo_anterior_solo",
        ):
            cur = vista_actual
            st.session_state["modulo_actual"] = modulo_anterior
            st.session_state["modulo_anterior"] = cur
            st.rerun()

    elif paciente_sel:
        det_actual = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})

        with st.container(border=True):
            st.write(f"**{escape(str(paciente_sel))}**")
            st.caption(
                f"{escape(str(det_actual.get('empresa', mi_empresa)))}  ·  "
                f"DNI {escape(str(det_actual.get('dni', 'S/D')))}  ·  "
                f"{escape(str(det_actual.get('estado', 'Activo')))}"
            )


# ============================================================
# TOASTS
# ============================================================

from core.alert_toasts import render_queued_toasts

render_queued_toasts()


# ============================================================
# RENDER DE VISTA ACTUAL
# ============================================================

t0_view = time.monotonic()
ok_view = True

try:
    render_current_view(
        vista_actual,
        paciente_sel,
        mi_empresa,
        user,
        rol,
        menu_set,
    )

except Exception as exc:
    ok_view = False

    log_event(
        "main",
        f"render_current_view_fallo:{vista_actual}:{type(exc).__name__}:{exc}",
    )

    st.error(f"Error crítico al cargar el módulo **{vista_actual}**: {exc}")
    st.exception(exc)
    st.caption(f"Detalle técnico: {type(exc).__name__}: {exc}")

finally:
    record_perf(
        f"ui.modulo.{vista_actual}",
        (time.monotonic() - t0_view) * 1000.0,
        ok=ok_view,
    )


# ============================================================
# MÉTRICAS ADMIN
# ============================================================

if es_control_total(rol):
    with st.sidebar.expander("Rendimiento (ult. 15 min)", expanded=False):
        resumen_perf = summarize_perf(window_seconds=900)

        if not resumen_perf:
            st.caption("Sin métricas todavía.")
        else:
            for ev in sorted(resumen_perf.keys()):
                r = resumen_perf[ev]
                st.caption(
                    f"{ev} | n={r['count']} err={r['errors']} "
                    f"p50={r['p50_ms']}ms p95={r['p95_ms']}ms max={r['max_ms']}ms"
                )
