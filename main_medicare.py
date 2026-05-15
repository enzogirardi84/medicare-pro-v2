import base64
import json
import time
from datetime import datetime
from html import escape
from pathlib import Path

import streamlit as st

from core.app_bootstrap import insert_repo_root_on_path

insert_repo_root_on_path()

from core.app_logging import configurar_logging_basico, log_event

try:
    from core.error_tracker import setup_global_hooks, report_exception
except Exception as _exc_import_et:
    log_event("error_tracker", f"import_falla:{type(_exc_import_et).__name__}:{_exc_import_et}")
    setup_global_hooks = lambda: None
    def report_exception(**kwargs):
        pass
from core.app_navigation import (
    procesar_query_params_navegacion,
    render_current_view,
    render_module_nav,
    resolve_current_view,
    resolve_menu_for_role,
)
from core import utils as core_utils
from core.alertas_app_paciente_ui import render_banner_alertas_criticas_si_aplica
from core.anticolapso import limite_pacientes_sidebar
from core.auth import check_inactividad, render_login, verificar_clinica_sesion_activa
from core.notificaciones_superiores import render_franja_avisos_operativos
from core.release_notes import MC_APP_CHANGELOG
from core.app_performance import (
    procesar_guardado_pendiente_seguro,
    render_metricas_admin_sidebar,
)
from core.app_session import (
    eliminar_overlay_residual,
    inicializar_db_state_seguro,
    limpiar_sesion_app,
)
from core.app_theme import aplicar_css_base
from core.app_mobile import render_patient_selector
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
)
from core.ui_professional import apply_professional_theme
from core.view_registry import build_view_maps

APP_BUILD_TAG = "Build 2026-05-09 - Optimizado: velocidad, cache, UI"

st.set_page_config(
    page_title=PAGE_TITLE_PUBLIC,
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🩺",
)

# ============================================================
# OPTIMIZACIÓN DE RENDIMIENTO - Reducir re-renders
# ============================================================
# Solo aplicar theme una vez
if "theme_applied_v5" not in st.session_state:
    st.session_state["theme_applied_v5"] = False

configurar_logging_basico()

# Vigía de Errores: captura global de excepciones (sys.excepthook + threading)
try:
    setup_global_hooks()
except Exception as exc:
    log_event("error_tracker", f"setup_hooks_falla:{type(exc).__name__}:{exc}")

# ============================================================
# CSS GLOBAL
# ============================================================
aplicar_css_base()

# ============================================================
# ATAJOS DE TECLADO
# ============================================================
from core.atajos_teclado import inject_atajos_teclado, render_ayuda_atajos
inject_atajos_teclado()

# ============================================================
# HANDLER GLOBAL: Error conocido de imagen (Anthropic/IA)
# ============================================================
try:
    import streamlit as st
    # Verificar si LLM esta mal configurado
    from core.ai_assistant import LLM_ENABLED, LLM_PROVIDER, LLM_MODEL
    if LLM_ENABLED and LLM_PROVIDER:
        log_event("config", f"LLM configurado: {LLM_PROVIDER}/{LLM_MODEL}")
except Exception:
    pass

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
# SEGURIDAD: HTTPS, CSRF, Logs de acceso
# ============================================================
from core.seguridad_extendida import verificar_https, generar_csrf_token, registrar_acceso

verificar_https()
generar_csrf_token()  # Inicializar token CSRF para esta sesion

# Inicialización segura de variables críticas (evita KeyError en reruns parciales)
for _guard_key, _guard_default in (
    ("modulo_actual", None),
    ("paciente_actual", None),
):
    if _guard_key not in st.session_state:
        st.session_state[_guard_key] = _guard_default

# ============================================================
# TEMA PROFESIONAL POSLOGIN
# ============================================================
if not st.session_state.get("_mc_professional_theme_applied_v4"):
    try:
        apply_professional_theme()
        st.session_state["_mc_professional_theme_applied_v4"] = True
    except Exception as exc:
        log_event("ui_theme", f"Error aplicando tema: {exc}")
        try:
            report_exception(module="main.theme", exc_info=exc, context="apply_professional_theme()", severity="warning")
        except Exception:
            pass

# ============================================================
# GUARDADOS PENDIENTES
# ============================================================
try:
    procesar_guardado_pendiente_seguro()
except Exception as exc:
    log_event("main_rerun", f"procesar_guardado_pendiente_falla:{type(exc).__name__}:{exc}")
    try:
        report_exception(module="main.guardado_pendiente", exc_info=exc, context="procesar_guardado_pendiente_seguro()", severity="error")
    except Exception:
        pass

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
        try:
            report_exception(module="main.cache_cleanup", exc_info=exc, context="limpiar_cache_app()", severity="warning")
        except Exception:
            pass

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
    except OSError as exc:
        st.session_state[_logo_ck] = ""
        try:
            report_exception(module="main.logo", exc_info=exc, context="logo_sidebar_b64 read", severity="warning")
        except Exception:
            pass

logo_sidebar_b64 = st.session_state[_logo_ck]

if st.session_state.get("_modo_offline"):
    st.info(
        "Modo local activo. Los cambios se guardan en este equipo "
        "hasta configurar Supabase correctamente."
    )

# ============================================================
# SIDEBAR
# ============================================================
def _logout_callback():
    # Invalidar caches clinicos para prevenir fuga de datos entre sesiones
    for k in list(st.session_state.keys()):
        if k.startswith("_sql_clin_"):
            st.session_state.pop(k, None)
    for _key in ("u_actual", "modulo_actual", "paciente_actual"):
        st.session_state.pop(_key, None)
    st.session_state["_mc_logout_requested"] = True


with st.sidebar:
    st.button(
        "Cerrar sesión",
        width='stretch',
        key="sidebar_logout",
        on_click=_logout_callback,
    )

# Rerun limpio tras logout (fuera del contexto del botón para evitar desconexión websocket)
if st.session_state.pop("_mc_logout_requested", False):
    st.rerun()

# ============================================================
# OPTIMIZACIONES DE VELOCIDAD
# ============================================================
# Evitar reruns innecesarios en sidebar
if "sidebar_rendered" not in st.session_state:
    st.session_state["sidebar_rendered"] = True
else:
    # Skip reload if nothing changed
    pass

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

# ============================================================
# BIENVENIDA / ESTADO INICIAL (visible siempre)
# ============================================================
nombre_usuario = user.get("nombre", "Usuario")

paciente_sel = render_patient_selector(
    mi_empresa, rol, obtener_pacientes_visibles, mapa_detalles_pacientes
) or paciente_sel

# Grilla de módulos responsive (chunking nativo st.columns + CSS simple)
vista_actual = render_module_nav(menu, vista_actual, VIEW_NAV_LABELS, menu_set)

# Log de cambio de modulo
_modulo_prev = st.session_state.get("_modulo_anterior_log")
if _modulo_prev and _modulo_prev != vista_actual:
    registrar_acceso("cambio_modulo", f"{_modulo_prev} -> {vista_actual}")
st.session_state["_modulo_anterior_log"] = vista_actual

if not vista_actual:
    st.warning("No se pudo resolver un módulo visible para este usuario.")
    st.stop()

# Registrar acceso inicial solo una vez por sesion
if not st.session_state.get("_acceso_registrado"):
    registrar_acceso("login_ok", f"Modulo inicial: {vista_actual}")
    st.session_state["_acceso_registrado"] = True

# ============================================================
# BIENVENIDA / ESTADO SIN PACIENTE
# ============================================================
nombre_usuario = user.get("nombre", "Usuario")
if not paciente_sel:
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,rgba(14,165,233,0.1),rgba(37,99,235,0.05));border:1px solid rgba(14,165,233,0.2);border-radius:20px;padding:28px 24px;margin:10px 0 20px;text-align:center;">
        <h3 style="margin:0 0 8px;color:#e2e8f0;">Bienvenido, {nombre_usuario}</h3>
        <p style="margin:0 0 4px;color:#94a3b8;">Selecciona un paciente del selector superior para comenzar.</p>
        <p style="margin:0;color:#64748b;font-size:0.85rem;">Clinica: {mi_empresa} · Rol: {rol}</p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.caption(f"Paciente: **{paciente_sel}** — {mi_empresa}")

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
    def _swap_modulo_callback(cur, ant):
        st.session_state["modulo_actual"] = ant
        st.session_state["modulo_anterior"] = cur

    if mostrar_atajo and paciente_sel:
        col_nav, col_call = st.columns([1, 4])
        with col_nav:
            etiqueta_ant = VIEW_NAV_LABELS.get(modulo_anterior, modulo_anterior)
            st.button(
                "← Anterior",
                help=f"Volver a: {etiqueta_ant}",
                width='stretch',
                key="mc_atajo_modulo_anterior",
                on_click=_swap_modulo_callback,
                args=(vista_actual, modulo_anterior),
            )
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
        st.button(
            f"← Volver a {etiqueta_ant}",
            width='content',
            key="mc_atajo_modulo_anterior_solo",
            on_click=_swap_modulo_callback,
            args=(vista_actual, modulo_anterior),
        )
    elif paciente_sel:
        det_actual = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
        with st.container(border=True):
            st.write(f"**{escape(str(paciente_sel))}**")
            st.caption(
                f"{escape(str(det_actual.get('empresa', mi_empresa)))}  ·  "
                f"DNI {escape(str(det_actual.get('dni', 'S/D')))}  ·  "
                f"{escape(str(det_actual.get('estado', 'Activo')))}"
            )

# Backup automatico: verificar si pasaron 24h desde el ultimo
try:
    _ultimo_backup = st.session_state.get("_ultimo_backup_ts", 0)
    if time.time() - _ultimo_backup > 86400:  # 24h
        st.session_state["_ultimo_backup_ts"] = time.time()
        from core.database import _db_keys, dumps_db_sorted
        import json
        claves = _db_keys()
        data = {k: st.session_state[k] for k in claves if k in st.session_state}
        backup_path = Path(f"backups/auto_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        log_event("backup", f"auto_backup_ok:{backup_path.name}")
except Exception as exc:
    log_event("backup", f"auto_backup_fallo:{type(exc).__name__}:{exc}")

# ============================================================
# NOTIFICACIONES DE ESCRITORIO (browser push)
# ============================================================
st.markdown("""
<script>
if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission();
}
</script>
""", unsafe_allow_html=True)

# ============================================================
# TOASTS
# ============================================================
from core.alert_toasts import render_queued_toasts

render_queued_toasts()

# ============================================================
# PANEL DE SEGURIDAD / AUTO-BACKUP
# ============================================================
from core.seguridad_operaciones import render_panel_seguridad, deshacer_ultima_operacion

render_panel_seguridad()
render_ayuda_atajos()

# ============================================================
# BACKUP RAPIDO (visible siempre)
# ============================================================
if st.sidebar.button("Descargar Backup JSON", width='stretch', key="backup_rapido"):
    try:
        from core.database import _db_keys, dumps_db_sorted
        claves = _db_keys()
        data = {k: st.session_state[k] for k in claves if k in st.session_state}
        import json, io
        backup_str = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        st.sidebar.download_button(
            label="Guardar archivo",
            data=backup_str.encode("utf-8"),
            file_name=f"medicare_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
            width='stretch',
            key="download_backup"
        )
        log_event("backup", "backup_descargado")
    except Exception as exc:
        log_event("backup", f"error_backup:{type(exc).__name__}:{exc}")
        st.sidebar.error("Error al generar backup")

# Contador de notificaciones
_notif_count = len(st.session_state.get("_toast_queue", []))
if _notif_count > 0:
    st.sidebar.caption(f"🔔 {_notif_count} notificaciones pendientes")

# ============================================================
# AUTO-SCROLL AL CONTENIDO SI CAMBIÓ EL MÓDULO
# ============================================================
_modulo_previo_scroll = st.session_state.get("_mc_modulo_previo_scroll")
if _modulo_previo_scroll != vista_actual:
    st.session_state["_mc_modulo_previo_scroll"] = vista_actual
    # Scroll suave hacia el área de contenido (saltando la navegación superior)
    st.markdown(
        """<script>
            setTimeout(function() {
                try {
                    const main = window.parent.document.querySelector('.main');
                    if (!main) return;
                    const vb = main.querySelectorAll('[data-testid="stVerticalBlock"]');
                    // Buscar primer bloque que esté más allá de ~280px (zona navegación)
                    for (let i = 0; i < vb.length; i++) {
                        if (vb[i].offsetTop > 280) {
                            vb[i].scrollIntoView({ behavior: 'smooth', block: 'start' });
                            break;
                        }
                    }
                } catch(e) {}
            }, 350);
        </script>""",
        unsafe_allow_html=True,
    )

# ============================================================
# RENDER DE VISTA ACTUAL - con indicador visible
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
    try:
        report_exception(
            module=f"main.render_current_view.{vista_actual}",
            exc_info=exc,
            context=f"render_current_view({vista_actual}, paciente={paciente_sel})",
            severity="critical",
        )
    except Exception:
        pass
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
