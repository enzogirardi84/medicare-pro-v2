import base64
import io

import streamlit as st

from core.database import guardar_datos
from core.utils import (
    ahora,
    firma_a_base64,
    obtener_config_firma,
    optimizar_imagen_bytes,
    seleccionar_limite_registros,
)

CANVAS_DISPONIBLE = False
try:
    from streamlit_drawable_canvas import st_canvas
    CANVAS_DISPONIBLE = True
except ImportError:
    pass


def render_evolucion(paciente_sel, user, rol=None):
    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral.")
        return

    rol = rol or user.get("rol", "")
    puede_borrar = rol in {"Medico", "Coordinador", "SuperAdmin"}

    st.subheader("Evolucion Medica y Firma Digital")

    firma_subida = None
    if CANVAS_DISPONIBLE:
        st.markdown("##### Firma Digital del Paciente / Familiar")
        firma_cfg = obtener_config_firma("evolucion")
        metodo_firma = st.radio(
            "Metodo de firma",
            ["Subir foto de la firma (recomendado en celulares viejos)", "Firmar en pantalla"],
            horizontal=True,
            key="metodo_firma_evolucion",
        )
        firma_subida = None
        canvas_result = None
        if metodo_firma.startswith("Subir"):
            firma_subida = st.file_uploader(
                "Subir imagen de la firma",
                type=["png", "jpg", "jpeg"],
                key="firma_upload_evolucion",
            )
        else:
            st.caption("Usa el lienzo solo si el telefono responde fluido.")
            canvas_result = st_canvas(
                fill_color="rgba(255, 255, 255, 1)",
                stroke_width=firma_cfg["stroke_width"],
                stroke_color="#000000",
                background_color="#ffffff",
                height=firma_cfg["height"],
                width=firma_cfg["width"],
                drawing_mode="freedraw",
                display_toolbar=firma_cfg["display_toolbar"],
                key="canvas_firma_evolucion",
            )

        if st.button("Guardar Firma Digital", use_container_width=True, type="primary"):
            b64_firma = firma_a_base64(
                canvas_image_data=canvas_result.image_data if canvas_result is not None else None,
                uploaded_file=firma_subida,
            )

            if b64_firma:
                st.session_state["firmas_tactiles_db"].append({
                    "paciente": paciente_sel,
                    "fecha": ahora().strftime("%d/%m/%Y %H:%M"),
                    "firma_img": b64_firma,
                })
                guardar_datos()
                st.success("Firma guardada correctamente.")
                st.rerun()
            else:
                st.error("No se detecto una firma valida. Puedes subir una foto o usar el lienzo.")
    else:
        st.warning("Libreria de firma no disponible. Puedes subir una imagen de la firma.")
        firma_subida = st.file_uploader(
            "Subir imagen de la firma",
            type=["png", "jpg", "jpeg"],
            key="firma_upload_evolucion_sin_canvas",
        )

    st.divider()

    with st.form("evol", clear_on_submit=True):
        nota = st.text_area("Nota medica / Evolucion clinica", height=200, placeholder="Escribir aqui la evolucion...")
        col_foto1, col_foto2 = st.columns([3, 1])
        desc_w = col_foto1.text_input("Descripcion de la herida / lesion (opcional)")

        with col_foto2:
            st.markdown("Foto de la herida")
            usar_camara = st.checkbox("Encender camara")
            foto_w = st.camera_input("Tomar foto ahora", key="cam_evol") if usar_camara else None

        if st.form_submit_button("Firmar y Guardar Evolucion", use_container_width=True, type="primary"):
            if nota.strip():
                fecha_n = ahora().strftime("%d/%m/%Y %H:%M")
                st.session_state["evoluciones_db"].append({
                    "paciente": paciente_sel,
                    "nota": nota.strip(),
                    "fecha": fecha_n,
                    "firma": user["nombre"],
                })

                if foto_w is not None:
                    foto_bytes, _ = optimizar_imagen_bytes(foto_w.getvalue(), max_size=(1280, 1280), quality=70)
                    base64_foto = base64.b64encode(foto_bytes).decode("utf-8")
                    st.session_state["fotos_heridas_db"].append({
                        "paciente": paciente_sel,
                        "fecha": fecha_n,
                        "descripcion": desc_w.strip(),
                        "base64_foto": base64_foto,
                        "firma": user["nombre"],
                    })

                guardar_datos()
                st.success("Evolucion guardada correctamente.")
                st.rerun()
            else:
                st.error("La nota medica no puede estar vacia.")

    evs_paciente = [e for e in st.session_state.get("evoluciones_db", []) if e.get("paciente") == paciente_sel]
    if evs_paciente:
        st.divider()
        st.markdown("#### Historial de Evoluciones Clinicas")
        limite_evol = seleccionar_limite_registros(
            "Evoluciones a mostrar",
            len(evs_paciente),
            key=f"limite_evol_{paciente_sel}",
            default=20,
        )
        if puede_borrar:
            if st.button("Borrar ultima evolucion", use_container_width=True):
                if st.checkbox("Confirmar borrado", key="conf_del_evol"):
                    st.session_state["evoluciones_db"].remove(evs_paciente[-1])
                    guardar_datos()
                    st.rerun()
        else:
            st.caption("El borrado de evoluciones queda reservado a medico, coordinacion o administracion total.")

        st.caption(f"Mostrando {limite_evol} de {len(evs_paciente)} evoluciones registradas.")
        with st.container(height=560):
            for ev in reversed(evs_paciente[-limite_evol:]):
                with st.container(border=True):
                    st.markdown(f"**{ev['fecha']}** | **{ev['firma']}**")
                    st.write(ev["nota"])
                    st.caption("-" * 40)
    else:
        st.info("Aun no hay evoluciones registradas para este paciente.")
