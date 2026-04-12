import base64
import io

import streamlit as st

from core.database import guardar_datos
from core.utils import (
    ahora,
    contenedores_responsivos,
    decodificar_base64_seguro,
    firma_a_base64,
    limite_archivo_mb,
    modo_celular_viejo_activo,
    obtener_config_firma,
    puede_accion,
    preparar_imagen_clinica_bytes,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
    valor_por_modo_liviano,
)

CANVAS_DISPONIBLE = False
try:
    from streamlit_drawable_canvas import st_canvas
    CANVAS_DISPONIBLE = True
except ImportError:
    pass


def _auditar_evolucion(paciente_sel, user, accion, detalle, criticidad="media", referencia="", extra=None):
    registrar_auditoria_legal(
        "Evolucion Clinica",
        paciente_sel,
        accion,
        user.get("nombre", "Sistema"),
        user.get("matricula", ""),
        detalle,
        referencia=referencia,
        extra=extra or {},
        usuario=user,
        modulo="Evolucion",
        criticidad=criticidad,
    )


def render_evolucion(paciente_sel, user, rol=None):
    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral.")
        return

    rol = rol or user.get("rol", "")
    modo_liviano = modo_celular_viejo_activo()
    puede_registrar = puede_accion(rol, "evolucion_registrar")
    puede_borrar = puede_accion(rol, "evolucion_borrar")
    evs_paciente = [e for e in st.session_state.get("evoluciones_db", []) if e.get("paciente") == paciente_sel]
    fotos_heridas = [x for x in st.session_state.get("fotos_heridas_db", []) if x.get("paciente") == paciente_sel]

    st.subheader("Evolucion Medica y Firma Digital")
    if modo_liviano:
        st.caption("Modo celular viejo activo: la carga se simplifica, los adjuntos son opcionales y el historial usa menos memoria.")

    m1, m2, m3 = contenedores_responsivos(3, modo_liviano)
    m1.metric("Evoluciones", len(evs_paciente))
    m2.metric("Fotos clinicas", len(fotos_heridas))
    m3.metric("Ultimo registro", evs_paciente[-1]["fecha"] if evs_paciente else "Sin evoluciones")

    firma_subida = None
    canvas_result = None
    abrir_firma = st.checkbox(
        "Mostrar registro de firma del paciente / familiar",
        value=not modo_liviano,
        key="abrir_firma_evolucion",
    )
    if abrir_firma and CANVAS_DISPONIBLE:
        st.markdown("##### Firma Digital del Paciente / Familiar")
        firma_cfg = obtener_config_firma("evolucion", default_liviano=modo_liviano)
        metodo_firma = st.radio(
            "Metodo de firma",
            ["Subir foto de la firma (recomendado en celulares viejos)", "Firmar en pantalla"],
            horizontal=False,
            key="metodo_firma_evolucion",
        )
        firma_subida = None
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
    elif abrir_firma:
        st.warning("Libreria de firma no disponible. Puedes subir una imagen de la firma.")
        firma_subida = st.file_uploader(
            "Subir imagen de la firma",
            type=["png", "jpg", "jpeg"],
            key="firma_upload_evolucion_sin_canvas",
        )

    if abrir_firma and st.button("Guardar Firma Digital", use_container_width=True, type="primary"):
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
            _auditar_evolucion(
                paciente_sel,
                user,
                "Firma del paciente / familiar registrada",
                "Se registro una firma tactil o subida de imagen para dejar soporte documental de evolucion.",
                criticidad="alta",
                referencia="firma_evolucion",
                extra={"origen_firma": "canvas" if canvas_result is not None and firma_subida is None else "archivo"},
            )
            guardar_datos()
            st.success("Firma guardada correctamente.")
            st.rerun()
        else:
            st.error("No se detecto una firma valida. Puedes subir una foto o usar el lienzo.")

    st.divider()

    plantillas_evolucion = {
        "Libre": "",
        "Clinica general": "Motivo de la visita:\nSignos relevantes:\nConducta indicada:\nRespuesta del paciente:\nPlan y seguimiento:",
        "Enfermeria": "Procedimiento realizado:\nEstado general del paciente:\nSitio de acceso / curacion:\nTolerancia al procedimiento:\nIndicaciones para el proximo control:",
        "Heridas": "Ubicacion de la lesion:\nAspecto del lecho:\nExudado / olor:\nCuracion aplicada:\nEvolucion respecto al control previo:",
        "Respiratorio": "Saturacion actual:\nDispositivo / flujo de oxigeno:\nTrabajo respiratorio:\nAuscultacion:\nConducta y seguimiento:",
        "Pediatria": "Motivo de consulta:\nPeso / talla / temperatura:\nAlimentacion / hidratacion:\nEvaluacion general:\nPlan y recomendaciones:",
        "Cuidados paliativos": "Sintomas predominantes:\nDolor / confort:\nApoyo familiar:\nIntervenciones realizadas:\nPlan para las proximas horas:",
    }

    if puede_registrar:
        with st.form("evol", clear_on_submit=True):
            plantilla = st.selectbox("Plantilla de evolucion", list(plantillas_evolucion.keys()))
            if plantilla != "Libre":
                st.caption("Se carga una guia sugerida para agilizar el registro y mantener el formato clinico.")
            nota = st.text_area(
                "Nota medica / Evolucion clinica",
                value=plantillas_evolucion.get(plantilla, ""),
                height=220,
                placeholder="Escribir aqui la evolucion...",
            )
            col_foto1, col_foto2 = contenedores_responsivos([3, 1], modo_liviano)
            desc_w = col_foto1.text_input("Descripcion de la herida / lesion (opcional)")

            with col_foto2:
                st.markdown("Adjunto clinico")
                origen_foto = st.radio(
                    "Foto de herida / lesion",
                    ["No adjuntar", "Camara", "Subir archivo"],
                    horizontal=False,
                    key="origen_foto_evolucion",
                )
                foto_w = st.camera_input("Tomar foto ahora", key="cam_evol") if origen_foto == "Camara" else None
                foto_subida = (
                    st.file_uploader(
                        "Subir foto existente",
                        type=["png", "jpg", "jpeg"],
                        key="upload_foto_evolucion",
                    )
                    if origen_foto == "Subir archivo"
                    else None
                )
                st.caption(f"Imagen sugerida hasta {limite_archivo_mb('imagen')} MB.")

            if st.form_submit_button("Firmar y Guardar Evolucion", use_container_width=True, type="primary"):
                if nota.strip():
                    fecha_n = ahora().strftime("%d/%m/%Y %H:%M")
                    foto_preparada = None
                    origen_foto_guardado = ""
                    if foto_w is not None or foto_subida is not None:
                        bytes_foto = foto_w.getvalue() if foto_w is not None else foto_subida.getvalue()
                        nombre_foto = "camara_evolucion.jpg" if foto_w is not None else (foto_subida.name or "foto_evolucion.jpg")
                        origen_foto_guardado = "camara" if foto_w is not None else "archivo"
                        foto_preparada = preparar_imagen_clinica_bytes(
                            bytes_foto,
                            nombre_archivo=nombre_foto,
                            max_size=(1280, 1280),
                            quality=70,
                        )
                        if not foto_preparada["ok"]:
                            st.error(foto_preparada["error"])
                            return

                    registro_evolucion = {
                        "paciente": paciente_sel,
                        "nota": nota.strip(),
                        "fecha": fecha_n,
                        "firma": user["nombre"],
                        "plantilla": plantilla,
                    }

                    st.session_state["evoluciones_db"].append(registro_evolucion)
                    if foto_preparada is not None:
                        base64_foto = base64.b64encode(foto_preparada["bytes"]).decode("utf-8")
                        st.session_state["fotos_heridas_db"].append({
                            "paciente": paciente_sel,
                            "fecha": fecha_n,
                            "descripcion": desc_w.strip(),
                            "base64_foto": base64_foto,
                            "firma": user["nombre"],
                        })

                    _auditar_evolucion(
                        paciente_sel,
                        user,
                        "Nueva evolucion",
                        f"Se registro evolucion con plantilla {plantilla}.",
                        criticidad="media",
                        referencia=plantilla,
                        extra={
                            "plantilla": plantilla,
                            "adjunta_foto": foto_preparada is not None,
                            "origen_foto": origen_foto_guardado,
                            "longitud_nota": len(nota.strip()),
                        },
                    )
                    guardar_datos()
                    st.success("Evolucion guardada correctamente.")
                    st.rerun()
                else:
                    st.error("La nota medica no puede estar vacia.")
    else:
        st.caption("La carga de nuevas evoluciones queda deshabilitada para este rol.")

    if evs_paciente:
        st.divider()
        st.markdown("#### Historial de Evoluciones Clinicas")
        limite_evol = seleccionar_limite_registros(
            "Evoluciones a mostrar",
            len(evs_paciente),
            key=f"limite_evol_{paciente_sel}",
            default=valor_por_modo_liviano(20, 10),
        )
        if puede_borrar:
            col_chk, col_btn = contenedores_responsivos([1.2, 2.8], modo_liviano)
            confirmar_borrado = col_chk.checkbox("Confirmar", key="conf_del_evol")
            if col_btn.button("Borrar ultima evolucion", use_container_width=True, disabled=not confirmar_borrado):
                ultima = evs_paciente[-1]
                st.session_state["evoluciones_db"].remove(evs_paciente[-1])
                _auditar_evolucion(
                    paciente_sel,
                    user,
                    "Borrado de evolucion",
                    f"Se elimino la evolucion del {ultima.get('fecha', 'S/D')}.",
                    criticidad="alta",
                    referencia=ultima.get("fecha", ""),
                    extra={
                        "plantilla": ultima.get("plantilla", ""),
                        "firma_registro": ultima.get("firma", ""),
                    },
                )
                guardar_datos()
                st.rerun()
        else:
            st.caption("El borrado de evoluciones queda reservado a medico, coordinacion o administracion total.")

        st.caption(f"Mostrando {limite_evol} de {len(evs_paciente)} evoluciones registradas.")
        with st.container(height=valor_por_modo_liviano(560, 420)):
            for ev in reversed(evs_paciente[-limite_evol:]):
                with st.container(border=True):
                    st.markdown(f"**{ev['fecha']}** | **{ev['firma']}**")
                    if ev.get("plantilla"):
                        st.caption(f"Plantilla: {ev['plantilla']}")
                    st.write(ev["nota"])
                    st.caption("-" * 40)
    else:
        st.info("Aun no hay evoluciones registradas para este paciente.")

    if fotos_heridas:
        st.divider()
        st.markdown("#### Linea de tiempo de heridas y lesiones")
        limite_fotos = seleccionar_limite_registros(
            "Fotos a mostrar",
            len(fotos_heridas),
            key=f"limite_fotos_heridas_{paciente_sel}",
            default=valor_por_modo_liviano(12, 6),
            opciones=(6, 12, 20, 30),
        )
        mostrar_fotos = (not modo_liviano) or st.checkbox(
            "Cargar fotos de heridas",
            value=False,
            key=f"mostrar_fotos_evolucion_{paciente_sel}",
        )
        with st.container(height=valor_por_modo_liviano(520, 380)):
            for foto in reversed(fotos_heridas[-limite_fotos:]):
                with st.container(border=True):
                    st.markdown(f"**{foto.get('fecha', 'S/D')}** | **{foto.get('firma', 'Sin firma')}**")
                    if foto.get("descripcion"):
                        st.caption(foto.get("descripcion"))
                    if mostrar_fotos:
                        try:
                            imagen_bytes = decodificar_base64_seguro(foto.get("base64_foto", ""))
                            if not imagen_bytes:
                                raise ValueError("Foto vacia o invalida")
                            st.image(imagen_bytes, use_container_width=True)
                        except Exception:
                            st.warning("No se pudo mostrar una foto registrada.")
                    elif modo_liviano:
                        st.caption("Foto oculta para ahorrar memoria. Activa la carga solo si necesitas verla.")
