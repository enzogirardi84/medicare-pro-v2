"""Detección móvil y componentes adaptativos para móviles/tablets."""

import streamlit as st

from core.utils_pacientes import set_paciente_actual


# Cache simple UA en session_state para evitar reparseo
_UA_CACHE_KEY = "_mc_cache_ua_contexto"


def _get_ui_liviano_module():
    """Importa core.ui_liviano con fallback seguro."""
    try:
        import core.ui_liviano as ui_liv
        return ui_liv
    except Exception:
        pass
    try:
        from core import ui_liviano as ui_liv
        return ui_liv
    except Exception:
        return None


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


def render_mobile_patient_selector(mi_empresa, rol, obtener_pacientes_fn, mapa_detalles_fn):
    """Selector de pacientes para móviles (siempre visible, sin expander)."""
    if not cliente_es_movil_probable():
        return None

    es_tablet = cliente_es_tablet_probable()

    buscar = st.text_input(
        "Buscar paciente",
        placeholder="Nombre, DNI o palabra clave",
        key="mc_buscar_paciente_mobile",
    )

    p_f = obtener_pacientes_fn(
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

    valor_actual = st.session_state.get("paciente_actual")
    idx_actual = opciones.index(valor_actual) if valor_actual in opciones else 0

    st.caption("Paciente activo")
    paciente_sel_mobile = st.selectbox(
        "Seleccionar paciente",
        opciones,
        index=idx_actual,
        format_func=lambda x: display_map.get(x, x),
        label_visibility="collapsed",
    )

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
            f"{det.get('dni', 'S/D')}</span>",
            unsafe_allow_html=True,
        )
        cols_pac[1].markdown(
            f"<span style='font-size:.75rem;color:#94a3b8;'>"
            f"{det.get('obra_social', 'S/D')}</span>",
            unsafe_allow_html=True,
        )

    return paciente_sel_mobile if _cambio_paciente else None
