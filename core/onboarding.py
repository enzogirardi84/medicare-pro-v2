"""Panel de primeros pasos tras el login (una vez por sesión si el usuario lo cierra)."""

from html import escape

import streamlit as st


def _tips_por_rol(rol: str) -> list[str]:
    from core.utils import es_control_total

    r = str(rol or "").strip().lower()
    user = st.session_state.get("u_actual")
    if r in {"superadmin", "admin"}:
        return [
            "Revisá el **Dashboard** y el panel **Clínicas** para el estado de la red.",
            "Altas y correcciones de legajos en **Admisión**; permisos del equipo en **Mi Equipo**.",
            "**Auditoría** y **Auditoría Legal** centralizan rastros para soporte y cumplimiento.",
        ]
    if r in {"coordinador", "administrativo"} or (r == "operativo" and es_control_total(rol, user)):
        return [
            "**Visitas y Agenda** + **Asistencia en vivo** para coordinar el día.",
            "**Admisión** para pacientes; **RRHH** para fichajes y reportes.",
            "Con un paciente activo, **Historial** resume la trayectoria clínica.",
        ]
    return [
        "Elegí un **paciente activo** en la barra lateral antes de módulos clínicos.",
        "**Clínica**, **Evolución** y **Recetas** son el núcleo de la atención diaria.",
        "**PDF** y **Telemedicina** dependen de datos cargados en los módulos anteriores.",
    ]


def _clave_onboarding() -> str:
    usuario = st.session_state.get("u_actual") or "anon"
    return f"_mc_onboarding_oculto_{usuario}"


def render_panel_bienvenida(rol: str, menu: list[str], etiquetas_nav: dict[str, str]) -> None:
    from core.ui_liviano import headers_sugieren_equipo_liviano
    clave = _clave_onboarding()
    # Migrar clave vieja si existe
    if st.session_state.get("_mc_onboarding_oculto") and not st.session_state.get(clave):
        st.session_state[clave] = True
    if st.session_state.get(clave):
        return
    # En movil: solo mostrar si es la primera vez en la sesion (no expanded por defecto)
    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
    if es_movil and not st.session_state.get("_mc_onboarding_visto_movil"):
        st.session_state["_mc_onboarding_visto_movil"] = True
    tips = _tips_por_rol(rol)
    modulos_txt = []
    for m in menu[:8]:
        modulos_txt.append(escape(str(etiquetas_nav.get(m, m))))
    resto = max(0, len(menu) - 8)
    lista_mod = " · ".join(modulos_txt) if modulos_txt else "—"
    if resto:
        lista_mod += f" · (+{resto} más en el menú)"

    with st.expander("Primeros pasos en MediCare", expanded=not es_movil):
        st.markdown(
            f"""
            <div class="mc-onboarding-box">
                <p class="mc-onboarding-lead">Tu menú incluye: {lista_mod}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for t in tips:
            st.markdown(f"- {t}")
        st.caption("Los filtros y fechas suelen conservarse mientras la sesión sigue abierta (hasta Cerrar sesión).")
        c1, c2 = st.columns([1, 2])
        with c1:
            if st.button("Entendido, ocultar", use_container_width=True, key="mc_onboarding_cerrar"):
                st.session_state[clave] = True
                st.session_state["_mc_onboarding_oculto"] = True
                st.rerun()
        with c2:
            st.caption("Podés volver a ver ayuda contextual en cada módulo (bloques superiores).")
