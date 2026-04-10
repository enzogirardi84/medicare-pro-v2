import base64

import streamlit as st

from core.database import guardar_datos
from core.utils import ahora, optimizar_imagen_bytes, puede_accion, seleccionar_limite_registros


def _mismo_estudio(registro, objetivo):
    return (
        registro.get("paciente") == objetivo.get("paciente")
        and registro.get("fecha") == objetivo.get("fecha")
        and registro.get("tipo") == objetivo.get("tipo")
        and registro.get("detalle") == objetivo.get("detalle")
        and registro.get("firma") == objetivo.get("firma")
    )


def render_estudios(paciente_sel, user, rol=None):
    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral.")
        return

    rol = rol or user.get("rol", "")
    puede_registrar = puede_accion(rol, "estudios_registrar")
    puede_borrar = puede_accion(rol, "estudios_borrar")

    st.subheader("Ordenes y Resultados de Estudios")

    if puede_registrar:
        with st.form("form_estudios", clear_on_submit=True):
            col_e1, col_e2 = st.columns([1, 2])
            tipo_estudio = col_e1.selectbox("Tipo de Estudio", [
                "Laboratorio (Sangre/Orina)", "Radiografia (Rx)", "Ecografia",
                "Electrocardiograma (ECG)", "Tomografia (TAC)", "Resonancia Magnetica (RMN)", "Otro"
            ])
            detalle_estudio = col_e2.text_input("Detalle del Pedido o Resultado")

            st.markdown("##### Adjuntar Documento (Opcional)")
            archivo_subido = st.file_uploader("Subir archivo, foto de galeria o PDF", type=["png", "jpg", "jpeg", "pdf"], key="uploader_estudio")

            with st.expander("O tomar foto con la camara ahora", expanded=False):
                usar_cam = st.checkbox("Activar Camara")
                foto_estudio = st.camera_input("Tomar foto en vivo", key="camara_estudio") if usar_cam else None

            if st.form_submit_button("Guardar Estudio Clinico", use_container_width=True, type="primary"):
                img_b64 = ""
                ext = ""
                if archivo_subido is not None:
                    raw_bytes = archivo_subido.getvalue()
                    ext = archivo_subido.name.split('.')[-1].lower()
                    if ext in ["png", "jpg", "jpeg"]:
                        raw_bytes, ext_optimizada = optimizar_imagen_bytes(raw_bytes)
                        ext = ext_optimizada or ext
                    img_b64 = base64.b64encode(raw_bytes).decode("utf-8")
                elif foto_estudio is not None:
                    raw_bytes, ext_optimizada = optimizar_imagen_bytes(foto_estudio.getvalue())
                    img_b64 = base64.b64encode(raw_bytes).decode("utf-8")
                    ext = ext_optimizada or "jpg"

                st.session_state["estudios_db"].append({
                    "paciente": paciente_sel,
                    "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                    "tipo": tipo_estudio,
                    "detalle": detalle_estudio,
                    "imagen": img_b64,
                    "extension": ext,
                    "firma": user["nombre"],
                })
                guardar_datos()
                st.success("Estudio guardado correctamente.")
                st.rerun()
    else:
        st.caption("La carga de estudios queda deshabilitada para este rol.")

    estudios_pac = [e for e in st.session_state.get("estudios_db", []) if e["paciente"] == paciente_sel]

    if not estudios_pac:
        st.info("Aun no hay estudios guardados para este paciente.")
        return

    st.divider()
    st.markdown("#### Archivo de Estudios del Paciente")

    if puede_borrar:
        col_del1, col_del1_chk = st.columns([3, 1.2])
        confirmar_ultimo = col_del1_chk.checkbox("Confirmar ultimo", key="conf_del_ultimo_estudio")
        if col_del1.button("Borrar ultimo estudio", use_container_width=True, disabled=not confirmar_ultimo):
            st.session_state["estudios_db"].remove(estudios_pac[-1])
            guardar_datos()
            st.success("Estudio eliminado correctamente.")
            st.rerun()

        st.markdown("**Selecciona el estudio que quieres eliminar:**")
        opciones = []
        for est in reversed(estudios_pac[-200:]):
            label = f"{est['fecha']} - {est['tipo']}"
            if est.get("detalle"):
                label += f" | {est['detalle'][:50]}..."
            opciones.append((label, est))

        estudio_seleccionado = st.selectbox("Elegir estudio a borrar", options=opciones, format_func=lambda x: x[0], key="selector_borrar_estudio")
        col_sel_chk, col_sel_btn = st.columns([1.2, 2.8])
        confirmar_estudio = col_sel_chk.checkbox("Confirmar seleccion", key="conf_borrar_estudio")
        if col_sel_btn.button("Eliminar el estudio seleccionado", type="secondary", use_container_width=True, disabled=not confirmar_estudio):
            objetivo = estudio_seleccionado[1]
            st.session_state["estudios_db"] = [
                e for e in st.session_state["estudios_db"]
                if not _mismo_estudio(e, objetivo)
            ]
            guardar_datos()
            st.success("Estudio eliminado correctamente.")
            st.rerun()
    else:
        st.caption("La eliminacion de estudios queda reservada a medico, coordinacion o administracion total.")

    st.divider()
    limite_est = seleccionar_limite_registros(
        "Mostrar ultimos estudios",
        len(estudios_pac),
        key="lim_estudios_tab",
        default=20,
    )
    estudios_mostrar = estudios_pac[-limite_est:]
    cargar_multimedia = st.checkbox("Cargar imagenes y PDF adjuntos", value=False, key="cargar_estudios_adjuntos")
    st.caption(f"Mostrando {len(estudios_mostrar)} de {len(estudios_pac)} estudios cargados.")

    with st.container(height=520):
        for idx, est in enumerate(reversed(estudios_mostrar)):
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{est['fecha']}** | **{est['firma']}**")
                    st.markdown(f"**{est['tipo']}**")
                    if est.get("detalle"):
                        st.caption(est.get("detalle"))
                with col2:
                    if puede_borrar and st.button("Eliminar", key=f"del_est_{est['fecha']}_{idx}"):
                        st.session_state["estudios_db"] = [
                            e for e in st.session_state["estudios_db"]
                            if not _mismo_estudio(e, est)
                        ]
                        guardar_datos()
                        st.rerun()

                if cargar_multimedia and est.get("imagen"):
                    try:
                        img_bytes = base64.b64decode(est["imagen"])
                        if img_bytes.startswith(b"%PDF") or est.get("extension") == "pdf":
                            nombre_arch = f"Estudio_{est['fecha'][:10].replace('/', '-')}.pdf"
                            st.download_button("Descargar PDF", data=img_bytes, file_name=nombre_arch, mime="application/pdf", key=f"pdf_est_{est['fecha']}_{idx}", use_container_width=True)
                        else:
                            st.image(img_bytes, caption="Documento Adjunto", use_container_width=True)
                    except Exception:
                        st.error("Error al leer el archivo")
