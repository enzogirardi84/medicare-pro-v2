import streamlit as st

from core.utils import ahora
from core.view_helpers import aviso_sin_paciente, bloque_mc_grid_tarjetas


def render_telemedicina(paciente_sel):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Teleconsulta en vivo</h2>
            <p class="mc-hero-text">Sala Jitsi por paciente y dia. En celulares viejos o lentos abri siempre el enlace en pantalla completa; la vista embebida solo en PC fluidas.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Jitsi Meet</span>
                <span class="mc-chip">Pantalla completa</span>
                <span class="mc-chip">Camara / microfono</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Sala unica", "El enlace incluye paciente y fecha para evitar confusiones."),
            ("Celulares", "Preferi abrir Jitsi en pantalla completa desde el boton."),
            ("Integrada", "La vista embebida solo en PC o equipos fluidos."),
        ]
    )
    st.caption(
        "Comparti el enlace de la derecha con el paciente o familiar. La sala cambia cada dia (misma sala si todos entran el mismo dia). "
        "Permite camara y microfono cuando el navegador lo pida."
    )
    st.info("En celulares o equipos lentos conviene usar el boton de pantalla completa. La vista integrada queda como opcion.")

    nombre_limpio = "".join(e for e in paciente_sel if e.isalnum())
    fecha_hoy = ahora().strftime("%d%m%Y")
    sala_id = f"MediCare-{nombre_limpio}-{fecha_hoy}"
    jitsi_url = f"https://meet.jit.si/{sala_id}#config.disableDeepLinking=true&config.prejoinPageEnabled=false"

    c_vid1, c_vid2 = st.columns([3, 1])

    with c_vid1:
        st.markdown("### Sala de Video en Vivo")
        st.link_button("ABRIR VIDEOLLAMADA EN PANTALLA COMPLETA", jitsi_url, width='stretch', type="primary")
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
            st.html(iframe_html)

    with c_vid2:
        st.markdown("### Enlace para compartir")
        st.code(jitsi_url, language=None)

        if st.button("Copiar enlace de la sala", width='stretch'):
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
            st.warning(
                "No hay signos vitales cargados para este paciente. Para ver datos aca, registra un control en **Clinica (signos vitales)** antes o durante la teleconsulta."
            )
