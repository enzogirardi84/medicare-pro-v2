import base64
import sys
import traceback
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

from core.app_logging import configurar_logging_basico, log_event

configurar_logging_basico()

_core_auth = import_module("core.auth")
check_inactividad = _core_auth.check_inactividad
render_login = _core_auth.render_login
verificar_clinica_sesion_activa = getattr(_core_auth, "verificar_clinica_sesion_activa", lambda: None)

core_utils = import_module("core.utils")

_core_database = import_module("core.database")
obtener_estado_guardado = getattr(_core_database, "obtener_estado_guardado", lambda: {})
completar_claves_db_session = getattr(_core_database, "completar_claves_db_session", lambda: None)

_vr = import_module("core.view_roles")
MODULO_ROLES_PERMITIDOS = _vr.MODULO_ROLES_PERMITIDOS
tiene_acceso_vista = _vr.tiene_acceso_vista

ui_liv = import_module("core.ui_liviano")
headers_sugieren_equipo_liviano = ui_liv.headers_sugieren_equipo_liviano
render_mc_liviano_cliente = ui_liv.render_mc_liviano_cliente

_lpub = import_module("core.landing_publicidad")
obtener_html_landing_publicidad = _lpub.obtener_html_landing_publicidad

_onb = import_module("core.onboarding")
render_panel_bienvenida = _onb.render_panel_bienvenida

_ac = import_module("core.anticolapso")
aplicar_politicas_anticolapso_ui = _ac.aplicar_politicas_anticolapso_ui
anticolapso_activo_fn = _ac.anticolapso_activo
limite_pacientes_sidebar = _ac.limite_pacientes_sidebar
render_estabilidad_anticolapso_sidebar = _ac.render_estabilidad_anticolapso_sidebar

_aa = import_module("core.alertas_app_paciente_ui")
render_banner_alertas_criticas_si_aplica = _aa.render_banner_alertas_criticas_si_aplica
render_sidebar_bloque_app_paciente = _aa.render_sidebar_bloque_app_paciente

_rn = import_module("core.release_notes")
MC_APP_CHANGELOG = _rn.MC_APP_CHANGELOG

cargar_texto_asset = core_utils.cargar_texto_asset
es_control_total = getattr(
    core_utils,
    "es_control_total",
    lambda rol: str(rol or "").strip().lower() in {"superadmin", "admin", "coordinador", "administrativo"},
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

APP_BUILD_TAG = "Build 2026-04-14 landing st.html (evita bloque codigo Markdown)"

st.set_page_config(page_title="MediCare Enterprise PRO V9.12", layout="wide", initial_sidebar_state="collapsed")

try:
    st.markdown(f"<style>{cargar_texto_asset('style.css')}</style>", unsafe_allow_html=True)
except Exception:
    pass

if "_db_bootstrapped" not in st.session_state:
    # Sin precarga de PHI: monolito y multiclínica cargan la base en login / recuperación / tenant.
    inicializar_db_state(None, precargar_usuario_admin_emergencia=False)
    st.session_state["_db_bootstrapped"] = True

VIEW_CONFIG = {
    "Visitas y Agenda": ("views.visitas", "render_visitas"),
    "Dashboard": ("views.dashboard", "render_dashboard"),
    "Clinicas (panel global)": ("views.clinicas_panel", "render_clinicas_panel"),
    "Admision": ("views.admision", "render_admision"),
    "Clinica": ("views.clinica", "render_clinica"),
    "Enfermeria": ("views.enfermeria", "render_enfermeria"),
    "Pediatria": ("views.pediatria", "render_pediatria"),
    "Evolucion": ("views.evolucion", "render_evolucion"),
    "Estudios": ("views.estudios", "render_estudios"),
    "Materiales": ("views.materiales", "render_materiales"),
    "Recetas": ("views.recetas", "render_recetas"),
    "Balance": ("views.balance", "render_balance"),
    "Inventario": ("views.inventario", "render_inventario"),
    "Caja": ("views.caja", "render_caja"),
    "Emergencias y Ambulancia": ("views.emergencias", "render_emergencias"),
    "Alertas app paciente": ("views.alertas_paciente_app", "render_alertas_paciente_app"),
    "Red de Profesionales": ("views.red_profesionales", "render_red_profesionales"),
    "Escalas Clinicas": ("views.escalas_clinicas", "render_escalas_clinicas"),
    "Historial": ("views.historial", "render_historial"),
    "PDF": ("views.pdf_view", "render_pdf"),
    "Telemedicina": ("views.telemedicina", "render_telemedicina"),
    "Cierre Diario": ("views.cierre_diario", "render_cierre_diario"),
    "Mi Equipo": ("views.mi_equipo", "render_mi_equipo"),
    "Asistencia en Vivo": ("views.asistencia", "render_asistencia"),
    "RRHH y Fichajes": ("views.rrhh", "render_rrhh"),
    "Proyecto y Roadmap": ("views.project_management", "render_project_management"),
    "Auditoria": ("views.auditoria", "render_auditoria"),
    "Auditoria Legal": ("views.auditoria_legal", "render_auditoria_legal"),
}

VIEW_NAV_LABELS = {
    "Visitas y Agenda": "\U0001F4CD Visitas",
    "Dashboard": "\U0001F4CA Dashboard",
    "Clinicas (panel global)": "\U0001F3E5 Clinicas",
    "Admision": "\U0001FA7E Admision",
    "Clinica": "\U0001FA7A Clinica",
    "Enfermeria": "\U0001F469\U0000200D\U00002695\U0000FE0F Enfermeria",
    "Pediatria": "\U0001F476 Pediatria",
    "Evolucion": "\u270D\ufe0f Evolucion",
    "Estudios": "\U0001F9EA Estudios",
    "Materiales": "\U0001F4E6 Materiales",
    "Recetas": "\U0001F48A Recetas",
    "Balance": "\U0001F4A7 Balance",
    "Inventario": "\U0001F3E5 Inventario",
    "Caja": "\U0001F4B5 Caja",
    "Emergencias y Ambulancia": "\U0001F691 Emergencias",
    "Alertas app paciente": "\U0001F4F1 Alertas app",
    "Red de Profesionales": "\U0001F91D Red",
    "Escalas Clinicas": "\U0001F4CF Escalas",
    "Historial": "\U0001F5C2\ufe0f Historial",
    "PDF": "\U0001F4C4 PDF",
    "Telemedicina": "\U0001F3A5 Telemedicina",
    "Cierre Diario": "\U0001F9EE Cierre",
    "Mi Equipo": "\U0001F465 Equipo",
    "Asistencia en Vivo": "\U0001F6F0\ufe0f Asistencia",
    "RRHH y Fichajes": "\u23F1\ufe0f RRHH",
    "Proyecto y Roadmap": "\U0001F6E0\ufe0f Roadmap",
    "Auditoria": "\U0001F50E Auditoria",
    "Auditoria Legal": "\u2696\ufe0f Legal",
}

# Cada módulo en una sola categoría. Si agregás una entrada en VIEW_CONFIG, sumala acá
# (si no, el usuario solo la verá con el filtro «Todas las áreas»).
CATEGORIAS_MODULOS = {
    "Clínica": [
        "Visitas y Agenda",
        "Clinica",
        "Enfermeria",
        "Evolucion",
        "Estudios",
        "Recetas",
        "Escalas Clinicas",
        "Historial",
        "Pediatria",
        "Telemedicina",
    ],
    "Gestión": [
        "Dashboard",
        "Admision",
        "Inventario",
        "Materiales",
        "Cierre Diario",
        "Caja",
        "RRHH y Fichajes",
        "Clinicas (panel global)",
    ],
    "Emergencias": [
        "Emergencias y Ambulancia",
        "Alertas app paciente",
        "Asistencia en Vivo",
        "Red de Profesionales",
    ],
    "Legal y documentación": [
        "PDF",
        "Auditoria",
        "Auditoria Legal",
        "Proyecto y Roadmap",
        "Mi Equipo",
        "Balance",
    ],
}

CATEGORIAS_ORDEN = list(CATEGORIAS_MODULOS.keys())

_MC_FILTRO_TODAS = "Todas las áreas"


def _categorias_con_modulos_en_menu(menu):
    return [c for c in CATEGORIAS_ORDEN if any(m in menu for m in CATEGORIAS_MODULOS[c])]


def _etiqueta_filtro_categoria(nombre):
    if nombre == _MC_FILTRO_TODAS:
        return f"\U0001F5C2\ufe0f  {nombre}"
    prefijos = {
        "Clínica": "\U0001FA7A",
        "Gestión": "\U0001F4CA",
        "Emergencias": "\U0001F691",
        "Legal y documentación": "\u2696\ufe0f",
    }
    return f"{prefijos.get(nombre, '')}  {nombre}".strip()


def render_current_view(tab_name, paciente_sel, mi_empresa, user, rol):
    if tab_name not in resolve_menu_for_role(rol, user):
        st.error("No tienes permisos para acceder a este modulo.")
        return
    module_name, function_name = VIEW_CONFIG[tab_name]
    try:
        render_fn = getattr(import_module(module_name), function_name)
    except Exception as exc:
        st.error(f"No se pudo cargar el modulo '{tab_name}'.")
        st.caption(f"Detalle tecnico: {type(exc).__name__}: {exc}")
        return

    try:
        if tab_name == "Visitas y Agenda":
            render_fn(paciente_sel, mi_empresa, user, rol)
        elif tab_name == "Clinicas (panel global)":
            render_fn(mi_empresa, user, rol)
        elif tab_name == "Admision":
            render_fn(mi_empresa, rol)
        elif tab_name == "Clinica":
            render_fn(paciente_sel, user)
        elif tab_name == "Enfermeria":
            render_fn(paciente_sel, mi_empresa, user)
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
        elif tab_name == "Alertas app paciente":
            render_fn(mi_empresa, user, rol)
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
            render_fn(mi_empresa, rol, user)
        elif tab_name == "Asistencia en Vivo":
            render_fn(mi_empresa, user)
        elif tab_name == "RRHH y Fichajes":
            render_fn(mi_empresa, rol, user)
        elif tab_name == "Proyecto y Roadmap":
            render_fn(mi_empresa, user, rol)
        elif tab_name == "Auditoria":
            render_fn(mi_empresa, user)
        elif tab_name == "Auditoria Legal":
            render_fn(mi_empresa, user)
    except Exception as exc:
        log_event("ui", f"modulo_fallo:{tab_name}:{type(exc).__name__}")
        st.error(f"Fallo al abrir el modulo **{tab_name}**. El resto del sistema puede seguir en uso.")
        st.markdown(
            "**Sugerencias:** volver a elegir el modulo en la barra superior, recargar la pagina (**F5**), "
            "o cambiar de paciente si el error solo ocurre con uno. Si reaparece, envia el detalle tecnico a soporte."
        )
        with st.expander("Detalle tecnico (soporte o desarrollo)", expanded=False):
            st.code(f"{type(exc).__name__}: {exc}", language="text")
            st.code(traceback.format_exc(), language="text")
            st.caption(
                "Si ves **ImportError**, suele faltar instalar una dependencia en el servidor (requirements.txt)."
            )


def resolve_current_view(menu):
    if not menu:
        st.session_state.pop("modulo_actual", None)
        return None
    vista_actual = st.session_state.get("modulo_actual", menu[0])
    if vista_actual not in menu:
        vista_actual = menu[0]
    st.session_state["modulo_actual"] = vista_actual
    return vista_actual


def _sidebar_patient_card(paciente_sel, detalles):
    return (
        f'<div class="mc-patient-card">'
        f'<div class="mc-patient-card-kicker">Paciente activo</div>'
        f'<div class="mc-patient-card-name">{escape(paciente_sel)}</div>'
        f'<div class="mc-patient-card-meta">'
        f"DNI: {escape(detalles.get('dni', 'S/D'))}<br>"
        f"OS: {escape(detalles.get('obra_social', 'S/D'))}<br>"
        f"Empresa: {escape(detalles.get('empresa', 'S/D'))}<br>"
        f"Estado: {escape(detalles.get('estado', 'Activo'))}"
        f"</div>"
        f"</div>"
    )


def _sidebar_brand_card(mi_empresa, user, rol, descripcion, logo_sidebar_b64):
    logo_html = (
        f'<div class="mc-brand-logo-shell">'
        f'<img src="data:image/jpeg;base64,{logo_sidebar_b64}" class="mc-brand-logo" />'
        f"</div>"
        if logo_sidebar_b64
        else ""
    )
    return (
        f'<div class="mc-brand-card">'
        f"{logo_html}"
        f'<div class="mc-brand-kicker">MediCare Enterprise PRO</div>'
        f'<div class="mc-brand-company">{escape(mi_empresa)}</div>'
        f'<div class="mc-brand-user">{escape(user.get("nombre", ""))} <span>({escape(rol)})</span></div>'
        f'<div class="mc-brand-copy">{escape(descripcion)}</div>'
        f"</div>"
    )


def _parse_fecha_sidebar(fecha_txt):
    s = str(fecha_txt or "").strip()
    if not s:
        return datetime.min
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return datetime.min


def _render_sidebar_contexto_clinico(paciente_sel, vista_actual):
    vistas_clinicas = {"Recetas", "Clinica", "Enfermeria", "Evolucion", "Emergencias y Ambulancia"}
    if not paciente_sel or vista_actual not in vistas_clinicas:
        return

    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {}) or {}
    alergias = str(detalles.get("alergias", "") or "").strip()
    patologias = str(detalles.get("patologias", "") or detalles.get("diagnostico", "") or "").strip()

    vitales = [v for v in st.session_state.get("vitales_db", []) if v.get("paciente") == paciente_sel]
    vitales_orden = sorted(vitales, key=lambda x: _parse_fecha_sidebar(x.get("fecha", "")), reverse=True)[:3]

    st.sidebar.divider()
    st.sidebar.markdown(
        """
        <div class="mc-sidebar-section">
            <div class="mc-sidebar-kicker">Contexto clínico</div>
            <div class="mc-sidebar-title">Panel rápido del paciente</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if alergias:
        st.sidebar.error(f"Alergias: {alergias}")
    else:
        st.sidebar.caption("Alergias: sin datos.")

    st.sidebar.caption("Últimos signos vitales")
    if vitales_orden:
        for v in vitales_orden:
            ta = str(v.get("TA", "S/D") or "S/D")
            fc = str(v.get("FC", "S/D") or "S/D")
            temp = str(v.get("Temp", "S/D") or "S/D")
            fecha = str(v.get("fecha", "S/D") or "S/D")
            st.sidebar.markdown(f"- `{fecha}` · TA `{ta}` · FC `{fc}` · Temp `{temp}`")
    else:
        st.sidebar.caption("Sin registros vitales recientes.")

    st.sidebar.caption("Diagnósticos activos")
    if patologias:
        st.sidebar.markdown(f"- {escape(patologias)}")
    else:
        st.sidebar.caption("Sin diagnósticos cargados.")


def _render_sidebar_pacientes_y_alertas(mi_empresa, rol):
    st.markdown(
        """
        <div class="mc-sidebar-section">
            <div class="mc-sidebar-kicker">Pacientes</div>
            <div class="mc-sidebar-title">Buscador y seleccion</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    buscar = st.text_input("Buscar Paciente", placeholder="Nombre, DNI o palabra clave", key="mc_buscar_paciente")
    ver_altas = st.checkbox("Mostrar Pacientes de Alta", key="mc_ver_altas") if es_control_total(rol) else False

    p_f = obtener_pacientes_visibles(
        st.session_state,
        mi_empresa,
        rol,
        incluir_altas=ver_altas,
        busqueda=buscar,
    )
    limite_pacientes = valor_por_modo_liviano(limite_pacientes_sidebar(), 36, st.session_state)
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
        det_sidebar = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
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
                "<div class='mc-sidebar-alert-shell' style='max-height:360px; overflow-y:auto; padding-right:4px;'>"
                "<div class='mc-sidebar-title'>Alertas clinicas</div>"
                + "".join(bloques)
                + "</div>",
                unsafe_allow_html=True,
            )
    return paciente_sel


_fragment_api = getattr(st, "fragment", None)
if callable(_fragment_api):
    _render_sidebar_pacientes_y_alertas = _fragment_api(_render_sidebar_pacientes_y_alertas)


def render_module_nav(menu, vista_actual):
    if not menu:
        return None
    st.markdown(
        """
        <section class="mc-module-shell" aria-label="Navegacion principal de modulos">
            <div class="mc-module-shell-head">
                <span class="mc-module-shell-kicker">Navegacion</span>
                <h3 class="mc-module-shell-title">Modulos del sistema</h3>
                <p class="mc-module-shell-sub">Filtrá por área o mostrá todos los módulos habilitados para tu rol.</p>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    cats_ok = _categorias_con_modulos_en_menu(menu)
    filtro_opciones = [_MC_FILTRO_TODAS] + cats_ok

    if "mc_nav_filtro_cat" not in st.session_state or st.session_state["mc_nav_filtro_cat"] not in filtro_opciones:
        st.session_state["mc_nav_filtro_cat"] = _MC_FILTRO_TODAS

    filtro = st.selectbox(
        "Area del sistema",
        filtro_opciones,
        key="mc_nav_filtro_cat",
        format_func=_etiqueta_filtro_categoria,
        label_visibility="collapsed",
    )

    if filtro == _MC_FILTRO_TODAS:
        pill_options = list(menu)
        default_sel = vista_actual if vista_actual in pill_options else pill_options[0]
    else:
        mods_in_cat = [m for m in CATEGORIAS_MODULOS[filtro] if m in menu]
        if not mods_in_cat:
            st.caption("No hay módulos en esta área para tu usuario.")
            pill_options = list(menu)
            default_sel = vista_actual if vista_actual in pill_options else pill_options[0]
        elif vista_actual in mods_in_cat:
            pill_options = mods_in_cat
            default_sel = vista_actual
        else:
            pill_options = [vista_actual] + [m for m in mods_in_cat if m != vista_actual]
            default_sel = vista_actual

    selected = st.pills(
        "Modulos del sistema",
        pill_options,
        default=default_sel,
        selection_mode="single",
        format_func=lambda x: VIEW_NAV_LABELS.get(x, x),
        label_visibility="collapsed",
        key="module_nav_pills",
    )
    if selected and selected != vista_actual:
        st.session_state["modulo_anterior"] = vista_actual
        st.session_state["modulo_actual"] = selected
        return selected
    return selected or vista_actual


def resolve_menu_for_role(rol, user=None):
    if callable(obtener_modulos_permitidos):
        menu_base = obtener_modulos_permitidos(rol, list(VIEW_CONFIG), user) or []
    else:
        menu_base = list(VIEW_CONFIG)
    return [modulo for modulo in menu_base if modulo in VIEW_CONFIG]


def _query_flag(nombre):
    qp = getattr(st, "query_params", None)
    if qp is None:
        return False
    try:
        valor = qp.get(nombre)
        if isinstance(valor, list):
            valor = valor[0] if valor else ""
        return str(valor or "").strip().lower() in {"1", "true", "si", "yes", "on"}
    except Exception:
        return False


if "entered_app" not in st.session_state:
    # La publicidad vuelve a ser la portada por defecto.
    # Solo permitimos saltearla con un flag explicito para pruebas o accesos directos.
    st.session_state.entered_app = _query_flag("login") or _query_flag("directo")


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
            return f"<img src='data:{mime};base64,{encoded}' style='height: 112px; border-radius: 22px; box-shadow: 0 15px 35px rgba(0,0,0,0.45), 0 0 24px rgba(20,184,166,0.22); display: block;'>"

    svg = """
    <svg xmlns='http://www.w3.org/2000/svg' width='320' height='160' viewBox='0 0 320 160'>
      <defs>
        <linearGradient id='g1' x1='0%' y1='0%' x2='100%' y2='100%'>
          <stop offset='0%' stop-color='#14b8a6'/>
          <stop offset='100%' stop-color='#3b82f6'/>
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
    return f"<img src='data:image/svg+xml;base64,{encoded}' style='height: 112px; display: block;'>"


if not st.session_state.entered_app:
    logo_html = obtener_logo_landing()
    st.markdown(
        """
        <style>
            #MainMenu {visibility: hidden !important;}
            header[data-testid="stHeader"],
            [data-testid="stHeader"] {display: none !important;}
            [data-testid="stToolbar"],
            [data-testid="stDecoration"] {display: none !important;}
            div[data-testid="stToolbarActions"] {display: none !important;}
            .stDeployButton,
            [class*="stDeployButton"] {display: none !important;}
            footer,
            footer[data-testid="stFooter"] {visibility: hidden !important; height: 0 !important; min-height: 0 !important; overflow: hidden !important;}
            html, body, .stApp { overflow-x: hidden !important; }
            .block-container {
                padding-top: max(8px, env(safe-area-inset-top, 0px)) !important;
                padding-bottom: 0rem !important;
                max-width: 100% !important;
                margin-top: 0 !important;
                overflow: visible !important;
            }
            .stApp {
                background-color: #03050a !important;
                background-image:
                    radial-gradient(ellipse 100% 50% at 50% -15%, rgba(45, 212, 191, 0.08), transparent 50%),
                    radial-gradient(circle at 92% 8%, rgba(96, 165, 250, 0.1), transparent 40%),
                    linear-gradient(168deg, #03050a 0%, #060d18 100%) !important;
            }
            div.stButton { display: flex; justify-content: center; margin-top: 18px; padding-bottom: 42px; }
            div.stButton > button {
                min-height: 60px !important;
                min-width: 320px !important;
                padding: 0 34px !important;
                border-radius: 9999px !important;
                border: 1px solid rgba(186, 230, 253, 0.24) !important;
                background:
                    linear-gradient(135deg, rgba(18, 184, 166, 0.98) 0%, rgba(37, 99, 235, 0.98) 58%, rgba(56, 189, 248, 0.96) 100%) !important;
                color: white !important;
                font-size: 1rem !important;
                font-weight: 900 !important;
                text-transform: uppercase;
                letter-spacing: 0.18em;
                box-shadow:
                    0 18px 42px rgba(14, 165, 233, 0.22),
                    0 0 0 1px rgba(255,255,255,0.06) inset !important;
                transition: transform 0.25s ease, box-shadow 0.25s ease, filter 0.25s ease !important;
                backdrop-filter: blur(12px);
            }
            div.stButton > button:hover {
                transform: translateY(-3px) scale(1.01) !important;
                filter: brightness(1.04) !important;
                box-shadow:
                    0 24px 54px rgba(56, 189, 248, 0.28),
                    0 0 0 1px rgba(255,255,255,0.09) inset !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # st.markdown + HTML masivo puede mostrarse como bloque de codigo (GFM) en Streamlit 1.5x;
    # st.html inserta el fragmento sin pasar por el parser Markdown.
    _landing_html = obtener_html_landing_publicidad(logo_html)
    if hasattr(st, "html"):
        st.html(_landing_html, width="stretch")
    else:
        st.markdown(_landing_html, unsafe_allow_html=True)
    if st.button("\U0001F680 INGRESAR AL SISTEMA", key="btn_ingresar_main"):
        st.session_state.entered_app = True
        st.rerun()
    st.stop()

render_login()
verificar_clinica_sesion_activa()
check_inactividad()

user = st.session_state.get("u_actual")
# Dict no vacío: sesiones viejas o corruptas pueden dejar None, {} o tipos inválidos.
if not isinstance(user, dict) or not user:
    st.stop()

st.session_state.setdefault("modo_celular_viejo", False)
_canon = core_utils.normalizar_usuario_sistema(dict(user))
_merged = dict(user)
for _k in ("rol", "perfil_profesional", "empresa", "nombre", "email", "pin"):
    if _k in _canon and _canon.get(_k) != user.get(_k):
        _merged[_k] = _canon[_k]
_merged.setdefault("nombre", "Usuario sin nombre")
_merged.setdefault("empresa", "Clinica General")
_merged.setdefault("rol", "Administrativo")
st.session_state["u_actual"] = _merged
user = st.session_state.get("u_actual")
if not isinstance(user, dict) or not user:
    st.stop()

# Sesiones antiguas o JSON parcial: asegura colecciones nuevas sin borrar datos existentes.
completar_claves_db_session()

mi_empresa = str(user.get("empresa", "Clinica General") or "Clinica General")
rol = str(user.get("rol", "Administrativo") or "Administrativo")
logo_sidebar_path = Path(__file__).resolve().parent / "assets" / "logo_medicare_pro.jpeg"
try:
    logo_sidebar_b64 = (
        base64.b64encode(logo_sidebar_path.read_bytes()).decode() if logo_sidebar_path.exists() else ""
    )
except OSError:
    logo_sidebar_b64 = ""

if st.session_state.get("_modo_offline"):
    st.info("Modo local activo. Los cambios se guardan en este equipo hasta configurar Supabase correctamente.")

with st.sidebar:
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
        _sidebar_brand_card(
            mi_empresa,
            user,
            rol,
            descripcion_acceso_rol(rol, user),
            logo_sidebar_b64,
        ),
        unsafe_allow_html=True,
    )
    st.checkbox(
        "Modo celular viejo",
        key="modo_celular_viejo",
        help="Reduce listas y tablas visibles por pantalla. Complementa el **Modo anticolapso** (sidebar abajo): ambos pueden estar activos a la vez.",
    )
    if modo_celular_viejo_activo(st.session_state):
        st.caption("Modo celular viejo: menos datos por vista y listas de pacientes más cortas.")
    if anticolapso_activo_fn() and modo_celular_viejo_activo(st.session_state):
        st.caption("Anticolapso + celular viejo: máxima prioridad a estabilidad y memoria del navegador.")
    st.divider()

    render_estabilidad_anticolapso_sidebar()
    aplicar_politicas_anticolapso_ui()
    st.divider()

    menu = resolve_menu_for_role(rol, user)
    paciente_sel = _render_sidebar_pacientes_y_alertas(mi_empresa, rol)

    render_sidebar_bloque_app_paciente(mi_empresa, rol)

    st.divider()
    aplicar_politicas_anticolapso_ui()
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
        help="Automático: detecta Android antiguo, iOS ≤12, poca RAM, ahorro de datos y cabecera Save-Data. Modo liviano reduce sombras y animaciones. Con **anticolapso** activo, queda forzado en liviano.",
        label_visibility="collapsed",
    )
    st.session_state["mc_liviano_modo"] = _liv_vals[_liv_labels.index(_pick_liv)]
    # Tras el selectbox: si anticolapso está activo, volver a fijar liviano (evita un run con modo "off").
    aplicar_politicas_anticolapso_ui()
    if anticolapso_activo_fn():
        st.caption("**Anticolapso:** interfaz liviana fijada por política de sesión o servidor (`MC_ANTICOLAPSO`).")
    st.caption("Si el equipo es viejo, en «Automático» se activa solo un modo más liviano.")

    if st.button("Cerrar Sesion", use_container_width=True):
        limpiar_sesion_app()
        st.rerun()
    estado_guardado = obtener_estado_guardado()
    estado_clave = str(estado_guardado.get("estado", "") or "").strip().lower()
    timestamp_guardado = estado_guardado.get("timestamp")
    if timestamp_guardado:
        import datetime as _dt

        hora_guardado = _dt.datetime.fromtimestamp(timestamp_guardado).strftime("%H:%M:%S")
        if estado_clave == "nube":
            st.caption(f"Guardado: nube {hora_guardado}")
        elif estado_clave == "local":
            st.caption(f"Guardado: local {hora_guardado}")
        elif estado_clave == "error":
            st.caption(f"Guardado: error {hora_guardado}")
        elif estado_clave == "sin_cambios":
            st.caption(f"Sin cambios pendientes {hora_guardado}")
    detalle_guardado = str(estado_guardado.get("detalle", "") or "").strip()
    if detalle_guardado and estado_clave in {"local", "error"}:
        st.caption(detalle_guardado)
    st.caption(APP_BUILD_TAG)
    if es_control_total(rol):
        with st.expander("Notas de version (admin)", expanded=False):
            st.markdown(MC_APP_CHANGELOG)

_mc_srv_liviano = headers_sugieren_equipo_liviano()
render_mc_liviano_cliente(st.session_state.get("mc_liviano_modo", "auto"), _mc_srv_liviano)

vista_actual = resolve_current_view(menu)
if not vista_actual:
    st.warning("No hay modulos habilitados para este usuario. Revisa el rol asignado o la configuracion de permisos.")
    st.stop()
vista_actual = render_module_nav(menu, vista_actual)
if not vista_actual:
    st.warning("No se pudo resolver un modulo visible para este usuario.")
    st.stop()

_render_sidebar_contexto_clinico(paciente_sel, vista_actual)
render_panel_bienvenida(rol, menu, VIEW_NAV_LABELS)

render_banner_alertas_criticas_si_aplica(mi_empresa)

modulo_anterior = st.session_state.get("modulo_anterior")
mostrar_atajo = modulo_anterior and modulo_anterior in menu and modulo_anterior != vista_actual

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

render_current_view(vista_actual, paciente_sel, mi_empresa, user, rol)

