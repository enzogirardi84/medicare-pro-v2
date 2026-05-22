"""Detección móvil y componentes adaptativos para móviles/tablets."""


from __future__ import annotations

import time

from html import escape

import streamlit as st

from core.utils_pacientes import set_paciente_actual


# Cache simple UA en session_state para evitar reparseo
_UA_CACHE_KEY = "_mc_cache_ua_contexto"
_CSS_OPERATIVO_KEY = "_mc_mobile_css_operativo_v1"


def _get_ui_liviano_module():
    """Importa core.ui_liviano con fallback seguro."""
    try:
        import core.ui_liviano as ui_liv
        return ui_liv
    except ImportError:
        try:
            from core import ui_liviano as ui_liv
            return ui_liv
        except ImportError:
            return None


def _inyectar_css_mobile_operativo() -> None:
    """Parches mobile globales para uso clínico real desde teléfono."""
    if st.session_state.get(_CSS_OPERATIVO_KEY):
        return
    st.session_state[_CSS_OPERATIVO_KEY] = True
    st.markdown(
        """
        <style>
        @media screen and (max-width: 768px) {
            /* Quita la etiqueta técnica de debug para que no ocupe pantalla clínica. */
            .block-container::before { display: none !important; content: none !important; }

            /* Selectbox de paciente: compacto, legible y sin teclado invasivo. */
            div[data-baseweb="select"] div[role="combobox"] input {
                width: 1px !important;
                min-width: 1px !important;
                max-width: 1px !important;
                opacity: 0 !important;
                caret-color: transparent !important;
                pointer-events: none !important;
            }
            div[data-baseweb="select"] div[role="combobox"] > div,
            div[data-baseweb="select"] div[role="combobox"] span {
                max-width: calc(100vw - 5.5rem) !important;
                overflow: hidden !important;
                text-overflow: ellipsis !important;
                white-space: nowrap !important;
            }
            div[data-baseweb="popover"],
            div[data-baseweb="popover"] > div,
            div[data-baseweb="popover"] ul[role="listbox"],
            div[data-baseweb="popover"] div[role="listbox"] {
                width: calc(100vw - 1.3rem) !important;
                max-width: calc(100vw - 1.3rem) !important;
                max-height: min(52vh, 420px) !important;
                overflow-y: auto !important;
                overflow-x: hidden !important;
                -webkit-overflow-scrolling: touch !important;
                z-index: 2147483647 !important;
            }

            /* Cortina empresarial / data_editor: permite scroll real y toque de celdas. */
            [data-testid="stDataEditor"],
            [data-testid="stDataEditor"] > div,
            [data-testid="stDataFrame"],
            [data-testid="stDataFrame"] > div,
            .stDataEditor,
            .stDataFrame {
                width: 100% !important;
                max-width: 100% !important;
                overflow-x: auto !important;
                overflow-y: auto !important;
                -webkit-overflow-scrolling: touch !important;
                touch-action: pan-x pan-y !important;
                overscroll-behavior: contain !important;
            }
            [data-testid="stDataEditor"] canvas,
            [data-testid="stDataFrame"] canvas,
            [data-testid="stDataEditor"] [role="grid"],
            [data-testid="stDataFrame"] [role="grid"] {
                min-width: 760px !important;
                touch-action: pan-x pan-y !important;
                pointer-events: auto !important;
            }
            [data-testid="stDataEditor"] [role="gridcell"],
            [data-testid="stDataFrame"] [role="gridcell"] {
                min-height: 46px !important;
                touch-action: manipulation !important;
                pointer-events: auto !important;
            }

            /* Oculta overlays de Streamlit Cloud que tapan botones en teléfono. */
            [data-testid="stStatusWidget"],
            [data-testid="stDecoration"],
            .stDeployButton,
            .viewerBadge_container__1QSob,
            .viewerBadge_link__1S137,
            .viewerBadge_text__1JaDK {
                display: none !important;
                visibility: hidden !important;
                pointer-events: none !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _user_agent_contexto() -> str:
    """Devuelve el user-agent actual (con cache por rerun)."""
    cached = st.session_state.get(_UA_CACHE_KEY)
    if cached is not None:
        return cached
    ui_liv = _get_ui_liviano_module()
    ua = ""
    if ui_liv is not None:
        try:
            ua = ui_liv.user_agent_desde_contexto() or ""
        except Exception:
            pass
    st.session_state[_UA_CACHE_KEY] = ua
    return ua


def cliente_es_movil_probable() -> bool:
    """True si el cliente parece ser un teléfono móvil o tablet."""
    if st.session_state.get("mc_liviano_modo") == "on":
        return True

    # Fallback por headers (si existe en utils)
    try:
        from core.utils import headers_sugieren_equipo_liviano
        if headers_sugieren_equipo_liviano():
            return True
    except Exception:
        pass

    ui_liv = _get_ui_liviano_module()
    if ui_liv is not None:
        try:
            ua = _user_agent_contexto()
            return (
                ui_liv.user_agent_es_telefono_movil_probable(ua)
                or ui_liv.user_agent_es_tablet_probable(ua)
            )
        except Exception:
            pass
    return False


def cliente_es_tablet_probable() -> bool:
    """True si el cliente parece ser una tablet."""
    ui_liv = _get_ui_liviano_module()
    if ui_liv is not None:
        try:
            ua = _user_agent_contexto()
            return ui_liv.user_agent_es_tablet_probable(ua)
        except Exception:
            pass
    return False


def render_patient_selector(mi_empresa, rol, obtener_pacientes_fn, mapa_detalles_fn):
    """Selector de pacientes central compacto para mobile/tablet."""
    _inyectar_css_mobile_operativo()
    es_tablet = cliente_es_tablet_probable()

    # Cache de pacientes para evitar re-fetch en cada rerun.
    _cache_key = "_mc_pacientes_cache"
    _cache_ts_key = "_mc_pacientes_cache_ts"
    _cache_ttl = 5.0
    p_f = None
    _cached = st.session_state.get(_cache_key)
    _cached_ts = st.session_state.get(_cache_ts_key, 0.0)
    if _cached is not None and (time.time() - _cached_ts) < _cache_ttl:
        p_f = _cached
    if p_f is None:
        p_f = obtener_pacientes_fn(
            st.session_state,
            mi_empresa,
            rol,
            incluir_altas=False,
            busqueda="",
        )
        st.session_state[_cache_key] = p_f
        st.session_state[_cache_ts_key] = time.time()

    if not p_f:
        st.warning("No hay pacientes visibles.")
        return None

    opciones_todas = [item[0] for item in p_f]
    display_map_todos = {item[0]: item[1] for item in p_f}
    valor_actual = st.session_state.get("paciente_actual")
    idx_actual = opciones_todas.index(valor_actual) if valor_actual in opciones_todas else 0

    st.caption("Paciente activo")
    paciente_sel_mobile = st.selectbox(
        "Seleccionar paciente",
        opciones_todas,
        index=idx_actual,
        format_func=lambda x: display_map_todos.get(x, x),
        key="mc_paciente_select_mobile",
        help="Abrí la cortina y elegí el paciente. No se muestran todos como lista para no ocupar la pantalla.",
    )

    # Buscador opcional dentro de una cortina secundaria: solo se abre cuando hace falta filtrar.
    with st.expander("Buscar paciente por nombre o DNI", expanded=False):
        buscar = st.text_input(
            "Filtro de paciente",
            placeholder="Nombre, DNI o palabra clave",
            key="mc_buscar_paciente_mobile",
        )
        if buscar:
            p_filtrados = obtener_pacientes_fn(
                st.session_state,
                mi_empresa,
                rol,
                incluir_altas=False,
                busqueda=buscar,
            )
            limite = 25 if es_tablet else 8
            if len(p_filtrados) > limite:
                st.caption(f"Mostrando {limite} coincidencias. Escribí más para afinar.")
                p_filtrados = p_filtrados[:limite]
            if p_filtrados:
                opciones_filtradas = [item[0] for item in p_filtrados]
                display_map_filtrado = {item[0]: item[1] for item in p_filtrados}
                paciente_busqueda = st.selectbox(
                    "Resultado de búsqueda",
                    opciones_filtradas,
                    format_func=lambda x: display_map_filtrado.get(x, x),
                    key="mc_paciente_select_busqueda_mobile",
                )
                if st.button("Usar paciente encontrado", width="stretch", key="mc_usar_paciente_busqueda_mobile"):
                    paciente_sel_mobile = paciente_busqueda
                    set_paciente_actual(st.session_state, paciente_sel_mobile)
                    st.rerun()
            else:
                st.warning("No hay pacientes para ese filtro.")

    _cambio_paciente = (
        paciente_sel_mobile is not None
        and paciente_sel_mobile != st.session_state.get("paciente_actual")
    )
    if _cambio_paciente:
        set_paciente_actual(st.session_state, paciente_sel_mobile)

    if paciente_sel_mobile:
        det = mapa_detalles_fn(st.session_state).get(paciente_sel_mobile, {})
        cols_pac = st.columns([1, 3])
        cols_pac[0].markdown(
            f"<span style='font-size:.75rem;color:#94a3b8;'>"
            f"{escape(det.get('dni', 'S/D'))}</span>",
            unsafe_allow_html=True,
        )
        cols_pac[1].markdown(
            f"<span style='font-size:.75rem;color:#94a3b8;'>"
            f"{escape(det.get('obra_social', 'S/D'))}</span>",
            unsafe_allow_html=True,
        )

    return paciente_sel_mobile if _cambio_paciente else None
