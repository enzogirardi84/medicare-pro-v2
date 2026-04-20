import base64
import sys
import time
from datetime import datetime
from html import escape
from importlib import import_module
from pathlib import Path

def _insert_repo_root_on_path() -> Path:
    """
    Streamlit Cloud puede ejecutar main.py dentro de una subcarpeta (p. ej. main/main.py).
    Subimos directorios hasta encontrar `core/` (máx. 4 niveles) y lo anteponemos a sys.path.
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
    # También el directorio del script por si hay imports relativos a ese nivel
    hs = str(here)
    if hs != rs and hs not in sys.path:
        sys.path.insert(0, hs)
    return root


REPO_ROOT = _insert_repo_root_on_path()

import streamlit as st

from core.landing_runner import ensure_entered_app_default, render_publicidad_y_detener
from core.seo_streamlit import PAGE_TITLE_PUBLIC, inyectar_head_seo, inyectar_redirect_apex_si_configurado

APP_BUILD_TAG = "Build 2026-04-13 fast-path landing (imports diferidos)"

st.set_page_config(page_title=PAGE_TITLE_PUBLIC, layout="wide", initial_sidebar_state="collapsed")
inyectar_redirect_apex_si_configurado()
if not st.session_state.get("_mc_seo_head_inyectado"):
    inyectar_head_seo()
    st.session_state["_mc_seo_head_inyectado"] = True

ensure_entered_app_default()
if not st.session_state.get("entered_app"):
    render_publicidad_y_detener()

from core.feature_flags import ALERTAS_APP_PACIENTE_VISIBLE
from core.module_catalog import categorias_navegacion_sidebar
from core.view_registry import build_view_maps
from core.user_feedback import render_carga_modulo_fallo, render_modulo_fallo_ui

from core.app_logging import configurar_logging_basico, log_event
from core.perf_metrics import record_perf, summarize_perf
from core.ui_professional import configure_professional_page, apply_professional_theme

configurar_logging_basico()

# NOTA: apply_professional_theme() se difiere hasta después del login
# para que la pantalla de login cargue más rápido (ahorra ~25KB de CSS extra).
# Se aplica automáticamente al detectar sesión activa más abajo.

_core_auth = import_module("core.auth")
check_inactividad = _core_auth.check_inactividad
render_login = _core_auth.render_login
verificar_clinica_sesion_activa = getattr(_core_auth, "verificar_clinica_sesion_activa", lambda: None)

core_utils = import_module("core.utils")

_core_database = import_module("core.database")
obtener_estado_guardado = getattr(_core_database, "obtener_estado_guardado", lambda: {})
completar_claves_db_session = getattr(_core_database, "completar_claves_db_session", lambda: None)
procesar_guardado_pendiente = getattr(_core_database, "procesar_guardado_pendiente", lambda: False)

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
    lambda ss: ss.get("detalles_pacientes_db") if isinstance(ss.get("detalles_pacientes_db"), dict) else {},
)
obtener_alertas_clinicas = core_utils.obtener_alertas_clinicas
modo_celular_viejo_activo = getattr(core_utils, "modo_celular_viejo_activo", lambda session_state=None: False)
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
        if str(rol or "").strip().lower() in {"superadmin", "admin", "coordinador", "administrativo"}
        else "Acceso asistencial limitado al registro clinico del paciente"
    ),
)
obtener_modulos_permitidos = getattr(core_utils, "obtener_modulos_permitidos", None)
valor_por_modo_liviano = getattr(core_utils, "valor_por_modo_liviano", lambda normal, liviano, session_state=None: normal)

try:
    _css_path = Path(__file__).parent / "assets" / "style.css"
    _css_mtime = _css_path.stat().st_mtime if _css_path.exists() else 0.0
    st.markdown(f"<style>{cargar_texto_asset('style.css', _mtime=_css_mtime)}</style>", unsafe_allow_html=True)
except Exception:
    pass

# Modelo mobile unificado: se carga siempre, las @media queries internas lo activan solo en celular/tablet.
try:
    _mobile_css_path = Path(__file__).parent / "assets" / "mobile.css"
    if _mobile_css_path.exists():
        _mobile_mtime = _mobile_css_path.stat().st_mtime
        st.markdown(
            f"<style>{cargar_texto_asset('mobile.css', _mtime=_mobile_mtime)}</style>",
            unsafe_allow_html=True,
        )
except Exception:
    pass

# CSS legacy para browsers viejos (Android <=8, iOS <=12, sin :has ni clamp).
# Se activa solo cuando JS en ui_liviano.render_mc_liviano_cliente detecta browser antiguo
# y agrega la clase `mc-legacy` al elemento <html>. En browsers modernos no tiene efecto.
try:
    _legacy_css_path = Path(__file__).parent / "assets" / "mobile_legacy.css"
    if _legacy_css_path.exists():
        _legacy_mtime = _legacy_css_path.stat().st_mtime
        st.markdown(
            f"<style>{cargar_texto_asset('mobile_legacy.css', _mtime=_legacy_mtime)}</style>",
            unsafe_allow_html=True,
        )
except Exception:
    pass

if "_db_bootstrapped" not in st.session_state:
    # Sin precarga de PHI: monolito y multiclínica cargan la base en login / recuperación / tenant.
    inicializar_db_state(None, precargar_usuario_admin_emergencia=False)
    st.session_state["_db_bootstrapped"] = True

VIEW_CONFIG, VIEW_NAV_LABELS = build_view_maps(alertas_app_visible=ALERTAS_APP_PACIENTE_VISIBLE)

from core.nav_helpers import MC_FILTRO_TODAS  # noqa: F401  (referenciado en módulos heredados)
from core._ui_liviano_js import MOBILE_SIDEBAR_AUTOCLOSE_JS
from core.sidebar_components import (
    sidebar_brand_card as _sidebar_brand_card_fn,
    sidebar_patient_card as _sidebar_patient_card_fn,
    render_sidebar_contexto_clinico as _render_sidebar_contexto_clinico,
    render_sidebar_pacientes_y_alertas as _render_sidebar_pacientes_y_alertas_fn,
)
from core.view_dispatch import (
    render_current_view as _render_current_view_dispatch,
    resolve_current_view,
    render_module_nav as _render_module_nav_dispatch,
    resolve_menu_for_role as _resolve_menu_for_role_dispatch,
)


def render_current_view(tab_name, paciente_sel, mi_empresa, user, rol, menu_set=None):
    if menu_set is None:
        menu_set = frozenset(resolve_menu_for_role(rol, user))
    _render_current_view_dispatch(tab_name, paciente_sel, mi_empresa, user, rol, VIEW_CONFIG, menu_set)


def render_module_nav(menu, vista_actual, menu_set=None):
    return _render_module_nav_dispatch(menu, vista_actual, VIEW_NAV_LABELS, menu_set)


def resolve_menu_for_role(rol, user=None):
    return _resolve_menu_for_role_dispatch(rol, user, VIEW_CONFIG, obtener_modulos_permitidos)



def limpiar_sesion_app():
    from core.database import vaciar_datos_app_en_sesion
    from core.session_auth_cleanup import limpiar_estado_sesion_login_efimero

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
    limpiar_estado_sesion_login_efimero()
    vaciar_datos_app_en_sesion()
    st.session_state.pop("_mc_onboarding_oculto", None)
    st.session_state.pop("_db_monolito_sesion", None)
    st.session_state.pop("_mc_aviso_payload_grande", None)
    st.session_state.pop("mc_nav_filtro_cat", None)
    st.session_state.pop("_mc_sidebar_logo_b64", None)
    st.session_state.pop("_mc_anticolapso_secret_cached", None)
    st.session_state.pop("_mc_professional_theme_applied", None)
    st.session_state.pop("_mc_login_transition", None)
    st.session_state.pop("_mc_cache_headers_liviano", None)
    st.session_state.pop("_mc_cache_ua_contexto", None)
    st.session_state["entered_app"] = False


render_login()
verificar_clinica_sesion_activa()
check_inactividad()

user = st.session_state.get("u_actual")
# Dict no vacío: sesiones viejas o corruptas pueden dejar None, {} o tipos inválidos.
if not isinstance(user, dict) or not user:
    st.stop()

# Aplicar tema profesional solo cuando hay sesión activa (optimización de carga de login)
if not st.session_state.get("_mc_professional_theme_applied"):
    try:
        apply_professional_theme()
        st.session_state["_mc_professional_theme_applied"] = True
    except Exception as e:
        log_event("ui_theme", f"Error aplicando tema: {e}")

# Drena guardados agrupados por ráfaga sin bloquear formularios.
try:
    procesar_guardado_pendiente()
except Exception:
    pass

_canon = core_utils.normalizar_usuario_sistema(dict(user))
_merged = dict(user)
for _k in ("rol", "perfil_profesional", "empresa", "nombre", "email", "pin"):
    if _k in _canon and _canon.get(_k) != user.get(_k):
        _merged[_k] = _canon[_k]
_merged.setdefault("nombre", "Usuario sin nombre")
_merged.setdefault("empresa", "Clinica General")
_merged.setdefault("rol", "Operativo")
st.session_state["u_actual"] = _merged
user = st.session_state.get("u_actual")
if not isinstance(user, dict) or not user:
    st.stop()

# Imports de UI pesados solo con sesión válida (la pantalla de login no los necesita).
_ac = import_module("core.anticolapso")
aplicar_politicas_anticolapso_ui = _ac.aplicar_politicas_anticolapso_ui
anticolapso_activo_fn = _ac.anticolapso_activo
limite_pacientes_sidebar = _ac.limite_pacientes_sidebar
render_estabilidad_anticolapso_sidebar = _ac.render_estabilidad_anticolapso_sidebar

ui_liv = import_module("core.ui_liviano")
headers_sugieren_equipo_liviano = ui_liv.headers_sugieren_equipo_liviano
render_mc_liviano_cliente = ui_liv.render_mc_liviano_cliente
render_mobile_sidebar_toggle = ui_liv.render_mobile_sidebar_toggle

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

# Sesiones antiguas o JSON parcial: asegura colecciones nuevas sin borrar datos existentes.
completar_claves_db_session()

mi_empresa = str(user.get("empresa", "Clinica General") or "Clinica General")
rol = str(user.get("rol", "Operativo") or "Operativo")
_logo_ck = "_mc_sidebar_logo_b64"
if _logo_ck not in st.session_state:
    logo_sidebar_path = Path(__file__).resolve().parent / "assets" / "logo_medicare_pro.jpeg"
    try:
        st.session_state[_logo_ck] = (
            base64.b64encode(logo_sidebar_path.read_bytes()).decode() if logo_sidebar_path.exists() else ""
        )
    except OSError:
        st.session_state[_logo_ck] = ""
logo_sidebar_b64 = st.session_state[_logo_ck]

if st.session_state.get("_modo_offline"):
    st.info("Modo local activo. Los cambios se guardan en este equipo hasta configurar Supabase correctamente.")

with st.sidebar:
    st.caption(
        "Al **volver a la publicidad** o **cerrar sesión** se borran los datos clínicos en memoria "
        "de este navegador (recomendado en equipos compartidos)."
    )
    if st.button("Volver a la Publicidad", use_container_width=True):
        from core.database import vaciar_datos_app_en_sesion
        from core.session_auth_cleanup import limpiar_estado_sesion_login_efimero

        st.session_state.entered_app = False
        st.session_state["logeado"] = False
        for _k in ("u_actual", "paciente_actual", "modulo_actual", "modulo_anterior", "ultima_actividad"):
            st.session_state.pop(_k, None)
        limpiar_estado_sesion_login_efimero()
        vaciar_datos_app_en_sesion()
        st.rerun()
    st.divider()

    st.markdown(
        _sidebar_brand_card_fn(
            mi_empresa,
            user,
            rol,
            descripcion_acceso_rol(rol, user),
            logo_sidebar_b64,
        ),
        unsafe_allow_html=True,
    )
    st.divider()

    render_estabilidad_anticolapso_sidebar()
    st.divider()

    menu = resolve_menu_for_role(rol, user)
    paciente_sel = _render_sidebar_pacientes_y_alertas_fn(
        mi_empresa, rol,
        obtener_pacientes_fn=obtener_pacientes_visibles,
        obtener_alertas_fn=obtener_alertas_clinicas,
        mapa_detalles_fn=mapa_detalles_pacientes,
        es_control_total_fn=es_control_total,
        valor_por_modo_liviano_fn=valor_por_modo_liviano,
        limite_pacientes_fn=limite_pacientes_sidebar,
    )

    render_sidebar_bloque_app_paciente(mi_empresa, rol)

    st.divider()
    st.markdown(
        """
        <div class="mc-sidebar-section">
            <div class="mc-sidebar-kicker">Rendimiento</div>
            <div class="mc-sidebar-title">Equipos viejos o lentos</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _liv_opts = [
        ("Automático (detectar)", "auto"),
        ("Modo liviano siempre", "on"),
        ("Modo completo siempre", "off"),
    ]
    _liv_labels = [x[0] for x in _liv_opts]
    _liv_vals = [x[1] for x in _liv_opts]
    st.session_state.setdefault("mc_liviano_modo", "auto")
    _cur_liv = st.session_state["mc_liviano_modo"]
    _idx_liv = _liv_vals.index(_cur_liv) if _cur_liv in _liv_vals else 0
    _pick_liv = st.selectbox(
        "Modo interfaz",
        _liv_labels,
        index=_idx_liv,
        key="mc_liviano_select_ui",
        help="Automático: adapta sombras y animaciones según el equipo (navegador, RAM, Save-Data). En móviles viejos o con poco recurso se fuerza interfaz liviana.",
        label_visibility="collapsed",
    )
    st.session_state["mc_liviano_modo"] = _liv_vals[_liv_labels.index(_pick_liv)]
    # Aplicar politica una sola vez al final del bloque de configuracion de modo.
    aplicar_politicas_anticolapso_ui()
    if anticolapso_activo_fn():
        st.caption("**Estabilidad:** listas acotadas e interfaz liviana (detección automática o `MC_ANTICOLAPSO` en el servidor).")
    st.caption("En «Automático» el aspecto se ajusta al dispositivo sin controles extra en la barra lateral.")

    if st.button("Cerrar Sesion", use_container_width=True):
        limpiar_sesion_app()
        st.rerun()
    estado_guardado = obtener_estado_guardado()
    estado_clave = str(estado_guardado.get("estado", "") or "").strip().lower()
    timestamp_guardado = estado_guardado.get("timestamp")
    if timestamp_guardado:
        hora_guardado = datetime.fromtimestamp(timestamp_guardado).strftime("%H:%M:%S")
        if estado_clave == "nube":
            st.caption(f"Guardado: nube {hora_guardado}")
        elif estado_clave == "local":
            st.caption(f"Guardado: local {hora_guardado}")
        elif estado_clave == "error":
            st.caption(f"Guardado: error {hora_guardado}")
        elif estado_clave == "sin_cambios":
            st.caption(f"Sin cambios pendientes {hora_guardado}")
        elif estado_clave == "pendiente":
            st.caption(f"Guardado pendiente {hora_guardado}")
    detalle_guardado = str(estado_guardado.get("detalle", "") or "").strip()
    if detalle_guardado and estado_clave in {"local", "error"}:
        st.caption(detalle_guardado)
    st.caption(APP_BUILD_TAG)
    if es_control_total(rol):
        with st.expander("Notas de version (admin)", expanded=False):
            st.markdown(MC_APP_CHANGELOG)

# === Navegación móvil simplificada ===
# En pantallas pequeñas (móviles), el sidebar de Streamlit se comporta mal.
# Mostramos un menú expandible en el área principal para navegación rápida.
def _cliente_es_movil_probable():
    if st.session_state.get("mc_liviano_modo") == "on":
        return True
    if headers_sugieren_equipo_liviano():
        return True
    try:
        ua = ui_liv.user_agent_desde_contexto()
        return ui_liv.user_agent_es_telefono_movil_probable(ua) or ui_liv.user_agent_es_tablet_probable(ua)
    except Exception:
        return False


def _render_mobile_nav(menu, vista_actual, menu_set):
    """Menú hamburguesa simplificado para móviles y tablets en portrait."""
    # Detectar si parece móvil o tablet por el user agent
    es_movil = _cliente_es_movil_probable()
    if not es_movil:
        return None

    # Detectar si es tablet específicamente
    es_tablet = False
    try:
        ua = ui_liv.user_agent_desde_contexto()
        es_tablet = ui_liv.user_agent_es_tablet_probable(ua)
    except Exception:
        pass

    with st.expander("☰ Menú de navegación", expanded=False):
        st.caption("Seleccioná un módulo para navegar rápidamente:")
        # En tablets usar más columnas, en móvil solo 2
        cols_count = 3 if es_tablet else 2
        cols = st.columns(min(cols_count, len(menu)))
        for i, modulo in enumerate(menu):
            label = VIEW_NAV_LABELS.get(modulo, modulo)
            tipo = "primary" if modulo == vista_actual else "secondary"
            with cols[i % len(cols)]:
                if st.button(label, key=f"mobnav_{modulo}", use_container_width=True, type=tipo):
                    st.session_state["modulo_actual"] = modulo
                    st.rerun()
    return True


def _render_mobile_patient_selector(mi_empresa, rol):
    """Selector de pacientes alternativo para móviles donde el sidebar no es accesible."""
    es_movil = _cliente_es_movil_probable()
    if not es_movil:
        return None
    
    # Detectar si es tablet específicamente
    es_tablet = False
    try:
        ua = ui_liv.user_agent_desde_contexto()
        es_tablet = ui_liv.user_agent_es_tablet_probable(ua)
    except Exception:
        pass
    
    from core.utils import obtener_pacientes_visibles, mapa_detalles_pacientes
    
    with st.expander("👤 Selector de Paciente (Tocá para buscar)", expanded=(st.session_state.get("paciente_actual") is None)):
        st.caption("🔍 Buscá por nombre, DNI o empresa:")
        buscar = st.text_input("Buscar", placeholder="Nombre, DNI o palabra clave", key="mc_buscar_paciente_mobile")
        
        p_f = obtener_pacientes_visibles(
            st.session_state,
            mi_empresa,
            rol,
            incluir_altas=False,
            busqueda=buscar,
        )
        
        # Límite dinámico: más alto en tablets, más bajo en móviles
        limite_pacientes = 25 if es_tablet else 15
        if not buscar and len(p_f) > limite_pacientes:
            st.caption(f"Mostrando {limite_pacientes} pacientes. Escribí para filtrar.")
            p_f = p_f[:limite_pacientes]
        
        if not p_f:
            st.warning("No hay pacientes visibles")
            return None
        
        # Crear opciones para selectbox
        opciones = [item[0] for item in p_f]
        display_map = {item[0]: item[1] for item in p_f}
        
        paciente_sel = st.selectbox(
            "Seleccionar Paciente",
            opciones,
            format_func=lambda x: display_map.get(x, x),
            key="paciente_actual_select_mobile"
        )
        
        if paciente_sel and paciente_sel != st.session_state.get("paciente_actual"):
            st.session_state["paciente_actual"] = paciente_sel
            st.rerun()
        
        # Mostrar info del paciente seleccionado
        if paciente_sel:
            det = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
            st.success(f"👤 {paciente_sel}")
            st.caption(f"DNI: {det.get('dni', 'S/D')} | OS: {det.get('obra_social', 'S/D')}")
        
        return paciente_sel
    return None


# Overlay de transicion post-login: cubre el flash negro entre reruns
if st.session_state.pop("_mc_login_transition", False):
    st.markdown("""
<style>
#mc-login-transition-overlay{position:fixed;top:0;left:0;width:100vw;height:100vh;
background:#030609;display:flex;flex-direction:column;justify-content:center;
align-items:center;z-index:9999999;gap:16px;
animation:mc-tr-fadeout 0.55s ease 0.7s forwards;}
@keyframes mc-tr-fadeout{from{opacity:1}to{opacity:0;pointer-events:none;visibility:hidden;}}
.mc-tr-spinner{width:40px;height:40px;border:3px solid rgba(255,255,255,0.06);
border-left-color:#14b8a6;border-top-color:#60a5fa;border-radius:50%;
animation:mc-tr-spin 0.9s linear infinite;-webkit-animation:mc-tr-spin 0.9s linear infinite;
transform-origin:center center;will-change:transform;backface-visibility:hidden;-webkit-backface-visibility:hidden;}
.mc-tr-text{color:#94a3b8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
font-size:13px;font-weight:500;letter-spacing:0.3px;}
@keyframes mc-tr-spin{to{transform:rotate(360deg);}}
@-webkit-keyframes mc-tr-spin{to{transform:rotate(360deg);}}
</style>
<div id="mc-login-transition-overlay">
  <div class="mc-tr-spinner mc-spinner"></div>
  <span class="mc-tr-text">Cargando sistema...</span>
</div>
""", unsafe_allow_html=True)

menu_set = frozenset(menu)
vista_actual = resolve_current_view(menu, menu_set)

_mc_srv_liviano = headers_sugieren_equipo_liviano()
render_mc_liviano_cliente(st.session_state.get("mc_liviano_modo", "auto"), _mc_srv_liviano)
render_mobile_sidebar_toggle()

# Inyectar JS para cerrar el sidebar automáticamente en móviles
st.markdown(MOBILE_SIDEBAR_AUTOCLOSE_JS, unsafe_allow_html=True)


# Alerta de stock removida por pedido del usuario (molesta; el stock bajo se ve en Inventario).
# Se mantienen las demas notificaciones del sistema mas abajo.
# render_alerta_inventario_banda_superior(mi_empresa, menu)
if not vista_actual:
    st.warning("No hay modulos habilitados para este usuario. Revisa el rol asignado o la configuracion de permisos.")
    st.stop()
vista_actual = render_module_nav(menu, vista_actual, menu_set)
if not vista_actual:
    st.warning("No se pudo resolver un modulo visible para este usuario.")
    st.stop()

_render_sidebar_contexto_clinico(paciente_sel, vista_actual)
# Panel "Primeros pasos en MediCare" removido por pedido del usuario (molesto).
# render_panel_bienvenida(rol, menu, VIEW_NAV_LABELS)

render_banner_alertas_criticas_si_aplica(mi_empresa)
render_franja_avisos_operativos(mi_empresa)

modulo_anterior = st.session_state.get("modulo_anterior")
mostrar_atajo = modulo_anterior and modulo_anterior in menu_set and modulo_anterior != vista_actual

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
            st.markdown(
                f"""
                <div class="mc-callout">
                    <strong>Paciente activo:</strong> {escape(paciente_sel)}<br>
                    Empresa: {escape(det_actual.get('empresa', mi_empresa))} | DNI: {escape(det_actual.get('dni', 'S/D'))} | Estado: {escape(det_actual.get('estado', 'Activo'))}
                </div>
                """,
                unsafe_allow_html=True,
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
        st.markdown(
            f"""
            <div class="mc-callout">
                <strong>Paciente activo:</strong> {escape(paciente_sel)}<br>
                Empresa: {escape(det_actual.get('empresa', mi_empresa))} | DNI: {escape(det_actual.get('dni', 'S/D'))} | Estado: {escape(det_actual.get('estado', 'Activo'))}
            </div>
            """,
            unsafe_allow_html=True,
        )

from core.alert_toasts import render_queued_toasts
render_queued_toasts()

t0_view = time.monotonic()
ok_view = True
try:
    render_current_view(vista_actual, paciente_sel, mi_empresa, user, rol, menu_set)
except Exception:
    ok_view = False
    raise
finally:
    record_perf(f"ui.modulo.{vista_actual}", (time.monotonic() - t0_view) * 1000.0, ok=ok_view)

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
