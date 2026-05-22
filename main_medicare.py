from __future__ import annotations

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
from core.auth import check_inactividad, render_login, verificar_clinica_sesion_activa
from core.app_session import (
    eliminar_overlay_residual,
    inicializar_db_state_seguro,
)
from core.app_theme import aplicar_css_base
from core.app_performance import procesar_guardado_pendiente_seguro
from core.landing_runner import ensure_entered_app_default, render_publicidad_y_detener
from core.seo_streamlit import (
    PAGE_TITLE_PUBLIC,
    inyectar_head_seo,
    inyectar_redirect_apex_si_configurado,
)
from views.pwa_manifest import inject_pwa_headers
from core import utils as core_utils

APP_BUILD_TAG = "Build 2026-05-21 - Hide AI evolution controls"

st.set_page_config(
    page_title=PAGE_TITLE_PUBLIC,
    layout="wide",
    initial_sidebar_state="collapsed",
    page_icon="🩺",
)

if "theme_applied_v5" not in st.session_state:
    st.session_state["theme_applied_v5"] = False

configurar_logging_basico()

try:
    setup_global_hooks()
except Exception as exc:
    log_event("error_tracker", f"setup_hooks_falla:{type(exc).__name__}:{exc}")

aplicar_css_base()

from core.atajos_teclado import inject_atajos_teclado, render_ayuda_atajos
inject_atajos_teclado()

try:
    from core.ai_assistant import _get_llm_config, is_llm_enabled
    if is_llm_enabled():
        provider, api_key, model = _get_llm_config()
        log_event("config", f"LLM configurado: {provider}/{model}")
except Exception as exc:
    log_event("config", f"LLM init fallo: {type(exc).__name__}")

inyectar_redirect_apex_si_configurado()

if not st.session_state.get("_mc_seo_head_inyectado"):
    inyectar_head_seo()
    st.session_state["_mc_seo_head_inyectado"] = True

ensure_entered_app_default()

if not st.session_state.get("entered_app"):
    render_publicidad_y_detener()

eliminar_overlay_residual()
inicializar_db_state_seguro()

render_login()
verificar_clinica_sesion_activa()
check_inactividad()

user = st.session_state.get("u_actual")

if not isinstance(user, dict) or not user:
    st.stop()

from core.seguridad_extendida import verificar_https, generar_csrf_token, registrar_acceso

verificar_https()
generar_csrf_token()

for _guard_key, _guard_default in (
    ("modulo_actual", None),
    ("paciente_actual", None),
):
    if _guard_key not in st.session_state:
        st.session_state[_guard_key] = _guard_default

try:
    inject_pwa_headers()
except Exception as exc:
    log_event("pwa", f"inject_pwa_headers_falla:{type(exc).__name__}:{exc}")

try:
    mobile_css_path = Path(__file__).resolve().parent / "assets" / "mobile.css"
    if mobile_css_path.exists():
        mobile_css_content = mobile_css_path.read_text(encoding="utf-8")
        st.markdown(f"<style>{mobile_css_content}</style>", unsafe_allow_html=True)
except Exception as exc:
    log_event("mobile_css", f"carga_falla:{type(exc).__name__}:{exc}")

# Parche visual definitivo: elimina botones/avisos de IA de Evoluciones aunque
# aparezcan por caché, por un deploy viejo o por otro componente.
st.markdown("""
<script>
(function() {
  function hideAiEvolutionElements() {
    try {
      const doc = window.parent && window.parent.document ? window.parent.document : document;
      const phrases = [
        "Sugerir evolución con IA",
        "Sugerir evolucion con IA",
        "IA no disponible",
        "Configuración de IA",
        "Configuracion de IA",
        "Ajustes > Integraciones"
      ];
      const nodes = Array.from(doc.querySelectorAll("button, [data-testid='stButton'], [data-testid='stAlert'], div"));
      for (const node of nodes) {
        const txt = (node.innerText || node.textContent || "").trim();
        if (!txt) continue;
        if (phrases.some(p => txt.includes(p))) {
          let target = node.closest("[data-testid='stButton']") || node.closest("[data-testid='stAlert']") || node;
          target.style.setProperty("display", "none", "important");
          target.style.setProperty("visibility", "hidden", "important");
          target.style.setProperty("height", "0", "important");
          target.style.setProperty("min-height", "0", "important");
          target.style.setProperty("margin", "0", "important");
          target.style.setProperty("padding", "0", "important");
          target.style.setProperty("overflow", "hidden", "important");
        }
      }
    } catch (e) {}
  }
  hideAiEvolutionElements();
  setTimeout(hideAiEvolutionElements, 200);
  setTimeout(hideAiEvolutionElements, 700);
  setTimeout(hideAiEvolutionElements, 1400);
  setInterval(hideAiEvolutionElements, 1200);
  try {
    const doc = window.parent && window.parent.document ? window.parent.document : document;
    if (!window.__mcHideAiEvolutionObserver) {
      window.__mcHideAiEvolutionObserver = true;
      new MutationObserver(hideAiEvolutionElements).observe(doc.body, { childList: true, subtree: true });
    }
  } catch (e) {}
})();
</script>
""", unsafe_allow_html=True)

from core.ui_professional import apply_professional_theme
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

try:
    procesar_guardado_pendiente_seguro()
except Exception as exc:
    log_event("main_rerun", f"procesar_guardado_pendiente_falla:{type(exc).__name__}:{exc}")
    try:
        report_exception(module="main.guardado_pendiente", exc_info=exc, context="procesar_guardado_pendiente_seguro()", severity="error")
    except Exception:
        pass

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

from core.database import completar_claves_db_session, should_cleanup_cache, limpiar_cache_app

from core.app_navigation import (
    procesar_query_params_navegacion,
    render_current_view,
    render_module_nav,
    resolve_current_view,
    resolve_menu_for_role,
)
from core.alertas_app_paciente_ui import render_banner_alertas_criticas_si_aplica
from core.notificaciones_superiores import render_franja_avisos_operativos
from core.app_performance import (
    procesar_guardado_pendiente_seguro,
    render_metricas_admin_sidebar,
)
from core.app_mobile import render_patient_selector
from core.feature_flags import ALERTAS_APP_PACIENTE_VISIBLE
from core.nav_helpers import MC_FILTRO_TODAS  # noqa: F401
from core.perf_metrics import record_perf
from core.sidebar_components import (
    render_mobile_contexto_clinico as _render_mobile_contexto_clinico,
    render_sidebar_contexto_clinico as _render_sidebar_contexto_clinico,
)
from core.view_registry import build_view_maps

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

completar_claves_db_session()

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

mi_empresa = str(user.get("empresa", "Clinica General") or "Clinica General")
rol = str(user.get("rol", "Operativo") or "Operativo")

VIEW_CONFIG, VIEW_NAV_LABELS = build_view_maps(
    alertas_app_visible=ALERTAS_APP_PACIENTE_VISIBLE
)

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

def _logout_callback():
    st.session_state["logeado"] = False
    for k in list(st.session_state.keys()):
        if k.startswith("_sql_clin_") or k.startswith("_mc_"):
            st.session_state.pop(k, None)
    for _key in ("u_actual", "modulo_actual", "paciente_actual"):
        st.session_state.pop(_key, None)
    st.session_state["_mc_logout_requested"] = True

st.markdown('<div class="mc-mobile-only">', unsafe_allow_html=True)
if st.button("Cerrar sesión", key="mobile_logout", on_click=_logout_callback,
             use_container_width=True):
    pass
st.markdown('</div>', unsafe_allow_html=True)

with st.sidebar:
    st.button(
        "Cerrar sesión",
        width='stretch',
        key="sidebar_logout",
        on_click=_logout_callback,
    )

if st.session_state.pop("_mc_logout_requested", False):
    st.rerun()

if "sidebar_rendered" not in st.session_state:
    st.session_state["sidebar_rendered"] = True
else:
    pass

menu = resolve_menu_for_role(rol, user, VIEW_CONFIG, obtener_modulos_permitidos)
menu_set = frozenset(menu)

procesar_query_params_navegacion(menu_set)

vista_actual = resolve_current_view(menu, menu_set)

if not vista_actual:
    st.warning(
        "No hay módulos habilitados para este usuario. "
        "Revisá el rol asignado o la configuración de permisos."
    )
    st.stop()

nombre_usuario = user.get("nombre", "Usuario")

paciente_sel = render_patient_selector(
    mi_empresa, rol, obtener_pacientes_visibles, mapa_detalles_pacientes
) or st.session_state.get("paciente_actual")

vista_actual = render_module_nav(menu, vista_actual, VIEW_NAV_LABELS, menu_set)

_modulo_prev = st.session_state.get("_modulo_anterior_log")
if _modulo_prev and _modulo_prev != vista_actual:
    registrar_acceso("cambio_modulo", f"{_modulo_prev} -> {vista_actual}")
st.session_state["_modulo_anterior_log"] = vista_actual

if not vista_actual:
    st.warning("No se pudo resolver un módulo visible para este usuario.")
    st.stop()

if not st.session_state.get("_acceso_registrado"):
    registrar_acceso("login_ok", f"Modulo inicial: {vista_actual}")
    st.session_state["_acceso_registrado"] = True

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
    _render_mobile_contexto_clinico(paciente_sel)

_render_sidebar_contexto_clinico(paciente_sel, vista_actual)

render_banner_alertas_criticas_si_aplica(mi_empresa)
render_franja_avisos_operativos(mi_empresa)

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
        col_nav, col_call = st.columns([1, 3])
        with col_nav:
            etiqueta_ant = VIEW_NAV_LABELS.get(modulo_anterior, modulo_anterior)
            st.button(
                "←",
                help=f"Volver a: {etiqueta_ant}",
                use_container_width=True,
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

try:
    _ultimo_backup = st.session_state.get("_ultimo_backup_ts", 0)
    if time.time() - _ultimo_backup > 86400:
        st.session_state["_ultimo_backup_ts"] = time.time()
        from core.database import _db_keys
        claves = _db_keys()
        data = {k: st.session_state[k] for k in claves if k in st.session_state}
        backup_path = Path(f"backups/auto_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        log_event("backup", f"auto_backup_ok:{backup_path.name}")
except Exception as exc:
    log_event("backup", f"auto_backup_fallo:{type(exc).__name__}:{exc}")

st.markdown("""
<script>
if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission();
}
</script>
""", unsafe_allow_html=True)

_unsaved = st.session_state.get("_guardar_datos_pendiente", False) or st.session_state.get("_draft_pending", False)
if _unsaved:
    st.markdown("""
    <script>
    window.addEventListener('beforeunload', function(e) {
        e.preventDefault();
        e.returnValue = '';
    });
    </script>
    """, unsafe_allow_html=True)

from core.alert_toasts import render_queued_toasts

render_queued_toasts()

from core.seguridad_operaciones import render_panel_seguridad

render_panel_seguridad()
render_ayuda_atajos()

_do_backup = st.sidebar.button("Descargar Backup JSON", width='stretch', key="backup_rapido")
st.markdown('<div class="mc-mobile-only">', unsafe_allow_html=True)
_do_backup_mobile = st.button("Descargar Backup JSON", use_container_width=True, key="backup_rapido_mobile")
st.markdown('</div>', unsafe_allow_html=True)
if _do_backup or _do_backup_mobile:
    try:
        from core.database import _db_keys
        claves = _db_keys()
        data = {k: st.session_state[k] for k in claves if k in st.session_state}
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

_notif_count = len(st.session_state.get("_toast_queue", []))
if _notif_count > 0:
    st.sidebar.caption(f"🔔 {_notif_count} notificaciones pendientes")

if st.sidebar.button("⚙️ Configuración", use_container_width=True, key="sidebar_settings"):
    st.session_state["_show_settings"] = True
    st.rerun()

_modulo_previo_scroll = st.session_state.get("_mc_modulo_previo_scroll")
if _modulo_previo_scroll != vista_actual:
    st.session_state["_mc_modulo_previo_scroll"] = vista_actual
    st.markdown(
        """<script>
            setTimeout(function() {
                try {
                    const main = window.parent.document.querySelector('.main');
                    if (!main) return;
                    const vb = main.querySelectorAll('[data-testid="stVerticalBlock"]');
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

try:
    from core.self_healing import maybe_run_self_healing
    maybe_run_self_healing()
except Exception as exc:
    log_event("main", f"self_healing fallo: {type(exc).__name__}")

_label_modulo = VIEW_NAV_LABELS.get(vista_actual, vista_actual)
st.markdown(
    f'<div class="mc-mobile-only" style="text-align:center;margin-bottom:4px;">'
    f'<span style="background:rgba(20,184,166,0.15);color:#5eead4;padding:4px 14px;'
    f'border-radius:20px;font-size:0.82rem;font-weight:600;display:inline-block;">'
    f'{_label_modulo}</span></div>',
    unsafe_allow_html=True,
)

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
    st.error(f"Error al cargar el módulo **{vista_actual}**. Consulta los logs del sistema.")
    st.caption("Ocurrió un error inesperado. El equipo de soporte fue notificado.")
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

try:
    from views.ai_floating_assistant import render_ai_floating_assistant
    render_ai_floating_assistant(vista_actual, paciente_sel)
except Exception as exc:
    log_event("main", f"ai_floating_assistant fallo: {type(exc).__name__}")

if st.session_state.get("_show_settings", False):
    from views.settings import render_settings_page
    render_settings_page()
    if st.sidebar.button("⬅️ Volver al menú principal", use_container_width=True, key="settings_back"):
        st.session_state["_show_settings"] = False
        st.rerun()
    st.stop()

render_metricas_admin_sidebar(rol)
