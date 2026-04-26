"""Detección móvil y componentes adaptativos para móviles/tablets."""

import streamlit as st


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
    """Selector alternativo de pacientes para móviles (expander colapsable)."""
    if not cliente_es_movil_probable():
        return None

    es_tablet = cliente_es_tablet_probable()

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
            det = mapa_detalles_fn(st.session_state).get(paciente_sel_mobile, {})
            st.success(str(paciente_sel_mobile))
            st.caption(
                f"DNI: {det.get('dni', 'S/D')} | "
                f"OS: {det.get('obra_social', 'S/D')}"
            )

        return paciente_sel_mobile
    return None
