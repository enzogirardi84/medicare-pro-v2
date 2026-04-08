import streamlit as st
from core.utils import ahora


def render_telemedicina(paciente_sel):
    if not paciente_sel:
        st.info("Seleccione un paciente en el panel lateral para iniciar una teleconsulta.")
        return

    st.subheader("Teleconsulta en Vivo")
    st.info("En celulares o equipos lentos conviene usar el boton de pantalla completa. La vista integrada queda como opcion.")

    nombre_limpio = "".join(e for e in paciente_sel if e.isalnum())
    fecha_hoy = ahora().strftime("%d%m%Y")
    sala_id = f"MediCare-{nombre_limpio}-{fecha_hoy}"
    jitsi_url = f"https://meet.jit.si/{sala_id}#config.disableDeepLinking=true&config.prejoinPageEnabled=false"

    c_vid1, c_vid2 = st.columns([3, 1])

    with c_vid1:
        st.markdown("### Sala de Video en Vivo")
        st.link_button("ABRIR VIDEOLLAMADA EN PANTALLA COMPLETA", jitsi_url, use_container_width=True, type="primary")
        st.caption("Recomendado para celulares y tablets")
        mostrar_iframe = st.checkbox("Cargar vista integrada", value=False, help="Activalo solo en PC o si el equipo responde bien.")

        if mostrar_iframe:
            import streamlit.components.v1 as components

            st.divider()
            st.markdown("**Vista integrada (PC / Notebook):**")
            iframe_html = f"""
            <iframe src="{jitsi_url}" allow="camera; microphone; fullscreen; display-capture; autoplay"
                style="width: 100%; height: 520px; border: none; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);">
            </iframe>
            """
            components.html(iframe_html, height=540)

    with c_vid2:
        st.markdown("### Enlace para compartir")
        st.code(jitsi_url, language=None)

        if st.button("Copiar enlace de la sala", use_container_width=True):
            st.toast("Enlace copiado al portapapeles")
            st.session_state["clipboard"] = jitsi_url

        st.divider()
        st.markdown("### Resumen Clinico Inmediato")
        st.write(f"**Paciente:** {paciente_sel}")

        vitales_paciente = [v for v in st.session_state.get("vitales_db", []) if v.get("paciente") == paciente_sel]

        if vitales_paciente:
            ult = vitales_paciente[-1]
            st.success(f"**Ultimo control:** {ult.get('fecha', 'S/D')}")
            claves_excluidas = ["paciente", "fecha", "id", "observaciones", "firma"]
            cols_v = st.columns(2)
            i = 0
            for clave, valor in ult.items():
                if clave not in claves_excluidas and valor not in [None, "", " "]:
                    nombre_formateado = str(clave).replace("_", " ").title()
                    with cols_v[i % 2]:
                        st.metric(label=nombre_formateado, value=valor)
                    i += 1
        else:
            st.warning("Aun no hay signos vitales registrados para este paciente.")
