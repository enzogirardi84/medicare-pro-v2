import base64
import time
from html import escape
from importlib import import_module
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from core.app_bootstrap import insert_repo_root_on_path

insert_repo_root_on_path()

from core.app_logging import configurar_logging_basico, log_event
from core.app_navigation import (
    procesar_query_params_navegacion,
    render_current_view,
    render_module_nav,
    resolve_current_view,
    resolve_menu_for_role,
)
from core.app_performance import (
    guardar_datos_seguro,
    procesar_guardado_pendiente_seguro,
    render_metricas_admin_sidebar,
)
from core.app_session import (
    eliminar_overlay_residual,
    inicializar_db_state_seguro,
    limpiar_sesion_app,
    reset_total_app,
)
from core.app_theme import aplicar_css_base
from core.app_mobile import cliente_es_movil_probable, render_mobile_patient_selector
from core.feature_flags import ALERTAS_APP_PACIENTE_VISIBLE
from core.landing_runner import ensure_entered_app_default, render_publicidad_y_detener
from core.nav_helpers import MC_FILTRO_TODAS  # noqa: F401
from core.perf_metrics import record_perf
from core.seo_streamlit import (
    PAGE_TITLE_PUBLIC,
    inyectar_head_seo,
    inyectar_redirect_apex_si_configurado,
)
from core.sidebar_components import (
    render_sidebar_contexto_clinico as _render_sidebar_contexto_clinico,
    render_sidebar_pacientes_y_alertas as _render_sidebar_pacientes_y_alertas_fn,
)
from core.ui_professional import apply_professional_theme
from core.view_registry import build_view_maps

APP_BUILD_TAG = "Build 2026-04-26 refactor: core/app_*.py + nav grid + sin duplicados"

st.set_page_config(
    page_title=PAGE_TITLE_PUBLIC,
    layout="wide",
    initial_sidebar_state="expanded",
)

configurar_logging_basico()

# ============================================================
# CSS GLOBAL
# ============================================================
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
    _core_auth, "verificar_clinica_sesion_activa", lambda: None
)

core_utils = import_module("core.utils")
cargar_texto_asset = core_utils.cargar_texto_asset
es_control_total = getattr(core_utils, "es_control_total", lambda rol, usuario_actual=None: str(rol or "").strip().lower() in {"superadmin", "admin", "coordinador", "administrativo"})
inicializar_db_state = core_utils.inicializar_db_state
mapa_detalles_pacientes = getattr(core_utils, "mapa_detalles_pacientes", lambda ss: ss.get("detalles_pacientes_db") if isinstance(ss.get("detalles_pacientes_db"), dict) else {})
obtener_alertas_clinicas = core_utils.obtener_alertas_clinicas
obtener_modulos_permitidos = getattr(core_utils, "obtener_modulos_permitidos", None)
obtener_pacientes_visibles = getattr(core_utils, "obtener_pacientes_visibles", lambda session_state, mi_empresa, rol, incluir_altas=False, busqueda="": [])
valor_por_modo_liviano = getattr(core_utils, "valor_por_modo_liviano", lambda normal, liviano, session_state=None: normal)

descripcion_acceso_rol = getattr(
    core_utils, "descripcion_acceso_rol",
    lambda rol: (
        "Acceso de gestion y control total"
        if str(rol or "").strip().lower() in {"superadmin", "admin", "coordinador", "administrativo"}
        else "Acceso asistencial limitado al registro clinico del paciente"
    ),
)

_ac = import_module("core.anticolapso")
limite_pacientes_sidebar = _ac.limite_pacientes_sidebar

_aa = import_module("core.alertas_app_paciente_ui")
render_banner_alertas_criticas_si_aplica = _aa.render_banner_alertas_criticas_si_aplica

_ns = import_module("core.notificaciones_superiores")
render_franja_avisos_operativos = _ns.render_franja_avisos_operativos

_rn = import_module("core.release_notes")
MC_APP_CHANGELOG = _rn.MC_APP_CHANGELOG

# ============================================================
# SESIÓN / BOOTSTRAP DB
# ============================================================
eliminar_overlay_residual()

inicializar_db_state_seguro()

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
    procesar_guardado_pendiente_seguro()
except Exception as exc:
    log_event("main_rerun", f"procesar_guardado_pendiente_falla:{type(exc).__name__}:{exc}")

# ============================================================
# NORMALIZAR USUARIO (solo si cambió)
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
from core.database import completar_claves_db_session, should_cleanup_cache, limpiar_cache_app

completar_claves_db_session()

# Limpieza automatica de caches si crecieron demasiado
if should_cleanup_cache():
    try:
        n = limpiar_cache_app()
        if n > 0:
            log_event("main_cache", f"limpieza_automatica:{n}_entradas")
    except Exception as exc:
        log_event("main_cache", f"limpieza_automatica_falla:{type(exc).__name__}:{exc}")

# ============================================================
# CONTEXTO USUARIO
# ============================================================
mi_empresa = str(user.get("empresa", "Clinica General") or "Clinica General")
rol = str(user.get("rol", "Operativo") or "Operativo")

# ============================================================
# VIEW MAPS
# ============================================================
VIEW_CONFIG, VIEW_NAV_LABELS = build_view_maps(
    alertas_app_visible=ALERTAS_APP_PACIENTE_VISIBLE
)

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
# BOTÓN FLOTANTE PACIENTES (móvil)
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
                    doc.querySelector('button[kind="header"]') ||
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
# SIDEBAR
# ============================================================
with st.sidebar:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Guardar", use_container_width=True, key="sidebar_guardar"):
            guardar_datos_seguro(spinner=True)
    with col2:
        if st.button("Abrir", use_container_width=True, key="sidebar_abrir"):
            reset_total_app()
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
menu = resolve_menu_for_role(rol, user, VIEW_CONFIG, obtener_modulos_permitidos)
menu_set = frozenset(menu)

# Query params nav (solo si cambió módulo realmente)
procesar_query_params_navegacion(menu_set)

vista_actual = resolve_current_view(menu, menu_set)

if not vista_actual:
    st.warning(
        "No hay módulos habilitados para este usuario. "
        "Revisá el rol asignado o la configuración de permisos."
    )
    st.stop()

# Selector alternativo en móvil
paciente_mobile = render_mobile_patient_selector(
    mi_empresa, rol, obtener_pacientes_visibles, mapa_detalles_pacientes
)

if paciente_mobile:
    paciente_sel = paciente_mobile

# Grilla de módulos responsive (HTML/CSS, sin st.columns ni st.pills)
vista_actual = render_module_nav(menu, vista_actual, VIEW_NAV_LABELS, menu_set)

if not vista_actual:
    st.warning("No se pudo resolver un módulo visible para este usuario.")
    st.stop()

# ============================================================
# CONTEXTO CLÍNICO / NOTIFICACIONES
# ============================================================
_render_sidebar_contexto_clinico(paciente_sel, vista_actual)

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
        VIEW_CONFIG,
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
render_metricas_admin_sidebar(rol)
