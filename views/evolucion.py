import base64
import io

import streamlit as st
from PIL import Image

from core.database import guardar_datos
from core.utils import ahora, optimizar_imagen_bytes

CANVAS_DISPONIBLE = False
try:
    from streamlit_drawable_canvas import st_canvas
    CANVAS_DISPONIBLE = True
except ImportError:
    pass


def render_evolucion(paciente_sel, user):
    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral.")
        return

    st.subheader("Evolucion Medica y Firma Digital")

    if CANVAS_DISPONIBLE:
        st.markdown("##### Firma Digital del Paciente / Familiar")
        canvas_result = st_canvas(
            fill_color="rgba(255, 255, 255, 1)",
            stroke_width=3,
            stroke_color="#000000",
            background_color="#ffffff",
            height=180,
            width=500,
            drawing_mode="freedraw",
            key="canvas_firma_evolucion",
        )

        if st.button("Guardar Firma Digital", use_container_width=True, type="primary"):
            if canvas_result.image_data is not None:
                img = Image.fromarray(canvas_result.image_data.astype("uint8"), "RGBA")
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[-1])
                buf = io.BytesIO()
                bg.save(buf, format="JPEG", optimize=True, quality=65)
                b64_firma = base64.b64encode(buf.getvalue()).decode("utf-8")

                st.session_state["firmas_tactiles_db"].append({
                    "paciente": paciente_sel,
                    "fecha": ahora().strftime("%d/%m/%Y %H:%M"),
                    "firma_img": b64_firma,
                })
                guardar_datos()
                st.success("Firma guardada correctamente.")
                st.rerun()
    else:
        st.warning("Libreria de firma no disponible.")

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
        if st.button("Borrar ultima evolucion", use_container_width=True):
            if st.checkbox("Confirmar borrado", key="conf_del_evol"):
                st.session_state["evoluciones_db"].remove(evs_paciente[-1])
                guardar_datos()
                st.rerun()

        for ev in reversed(evs_paciente):
            with st.container(border=True):
                st.markdown(f"**{ev['fecha']}** | **{ev['firma']}**")
                st.write(ev["nota"])
                st.caption("-" * 40)
    else:
        st.info("Aun no hay evoluciones registradas para este paciente.")
