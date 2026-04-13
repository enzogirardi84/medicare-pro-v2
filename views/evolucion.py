import base64
import html
import io

import streamlit as st
import streamlit.components.v1 as components

from core.database import guardar_datos
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, bloque_mc_grid_tarjetas
from core.utils import (
    ahora,
    firma_a_base64,
    obtener_config_firma,
    optimizar_imagen_bytes,
    puede_accion,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
)

CANVAS_DISPONIBLE = False
try:
    from streamlit_drawable_canvas import st_canvas
    CANVAS_DISPONIBLE = True
except ImportError:
    pass


def _historial_evoluciones_scroll_interno(evs_mas_recientes_primero, altura_iframe_px: int = 520):
    """
    Historial en iframe con altura fija: el scroll vive adentro (Streamlit suele romper overflow en st.markdown).
    """
    bloques = []
    for i, ev in enumerate(evs_mas_recientes_primero):
        fecha = html.escape(str(ev.get("fecha", "")))
        firma = html.escape(str(ev.get("firma", "")))
        nota = html.escape(str(ev.get("nota", "")))
        plantilla = ev.get("plantilla")
        margen = "0" if i == len(evs_mas_recientes_primero) - 1 else "0 0 12px 0"
        bloques.append(
            f'<div class="mc-evol-card" style="margin:{margen};">'
            f'<div class="mc-evol-meta"><b>{fecha}</b> | <b>{firma}</b></div>'
        )
        if plantilla:
            bloques.append(
                f'<div class="mc-evol-plant">Plantilla: {html.escape(str(plantilla))}</div>'
            )
        bloques.append(f'<div class="mc-evol-body">{nota}</div></div>')
    cards_html = "".join(bloques)

    doc = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"/>
<style>
  html, body {{ margin:0; height:100%; background:#0f172a; font-family:system-ui,-apple-system,sans-serif; }}
  .mc-evol-scroll {{
    height:100%; box-sizing:border-box; overflow-y:auto; overflow-x:hidden;
    -webkit-overflow-scrolling:touch; overscroll-behavior:contain;
    padding:14px 16px; border:1px solid rgba(148,163,184,0.4); border-radius:10px;
    background:rgba(30,41,59,0.5); scrollbar-gutter:stable;
  }}
  .mc-evol-card {{
    border:1px solid rgba(148,163,184,0.28); border-radius:8px; padding:12px 14px;
    background:rgba(15,23,42,0.65);
  }}
  .mc-evol-meta {{ color:#e2e8f0; font-size:14px; }}
  .mc-evol-plant {{ font-size:12px; color:#94a3b8; margin-top:6px; }}
  .mc-evol-body {{ color:#cbd5e1; font-size:14px; margin-top:10px; white-space:pre-wrap; word-break:break-word; }}
</style></head><body>
<div class="mc-evol-scroll">{cards_html}</div>
</body></html>"""

    components.html(doc, height=altura_iframe_px, scrolling=False)


def render_evolucion(paciente_sel, user, rol=None):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    rol = rol or user.get("rol", "")
    puede_registrar = puede_accion(rol, "evolucion_registrar")
    puede_borrar = puede_accion(rol, "evolucion_borrar")

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Evolucion medica</h2>
            <p class="mc-hero-text">Notas clinicas con firma del paciente o familiar y adjuntos. En celulares viejos preferi subir foto de firma antes que el lienzo tactil.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Firma digital</span>
                <span class="mc-chip">Historia</span>
                <span class="mc-chip">Auditoria legal</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Notas", "Registra evolucion con plantillas segun rol."),
            ("Firma", "En celulares lentos conviene foto de firma antes que el lienzo."),
            ("Auditoria", "Las altas quedan con trazabilidad legal."),
        ]
    )
    st.caption(
        "Primero podes registrar la firma del paciente o familiar (opcional). Debajo, la nota de evolucion con plantilla, foto de herida opcional y el historial al final."
    )

    firma_subida = None
    if CANVAS_DISPONIBLE:
        st.markdown("##### Firma Digital del Paciente / Familiar")
        firma_cfg = obtener_config_firma("evolucion")
        metodo_firma = st.radio(
            "Metodo de firma",
            ["Subir foto de la firma (recomendado en celulares viejos)", "Firmar en pantalla"],
            horizontal=False,
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
                        "plantilla": plantilla,
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

                    registrar_auditoria_legal(
                        "Evolucion Clinica",
                        paciente_sel,
                        "Nueva evolucion",
                        user.get("nombre", ""),
                        user.get("matricula", ""),
                        f"Se registro evolucion con plantilla {plantilla}.",
                    )
                    guardar_datos()
                    st.success("Evolucion guardada correctamente.")
                    st.rerun()
                else:
                    st.error("La nota medica no puede estar vacia.")
    else:
        st.caption("La carga de nuevas evoluciones queda deshabilitada para este rol.")

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
            col_chk, col_btn = st.columns([1.2, 2.8])
            confirmar_borrado = col_chk.checkbox("Confirmar", key="conf_del_evol")
            if col_btn.button("Borrar ultima evolucion", use_container_width=True, disabled=not confirmar_borrado):
                ultima = evs_paciente[-1]
                st.session_state["evoluciones_db"].remove(evs_paciente[-1])
                registrar_auditoria_legal(
                    "Evolucion Clinica",
                    paciente_sel,
                    "Borrado de evolucion",
                    user.get("nombre", ""),
                    user.get("matricula", ""),
                    f"Se elimino la evolucion del {ultima.get('fecha', 'S/D')}.",
                )
                guardar_datos()
                st.rerun()
        else:
            st.caption("El borrado de evoluciones queda reservado a medico, coordinacion o administracion total.")

        st.caption(
            f"Mostrando {limite_evol} de {len(evs_paciente)} evoluciones registradas. "
            "El panel gris tiene altura fija: con muchas notas el desplazamiento es dentro de ese panel (barra a la derecha del recuadro)."
        )
        _historial_evoluciones_scroll_interno(list(reversed(evs_paciente[-limite_evol:])))
    else:
        bloque_estado_vacio(
            "Sin evoluciones todavía",
            "Este paciente no tiene evoluciones médicas registradas.",
            sugerencia="Usá el formulario de arriba para cargar la primera evolución con firma.",
        )

    fotos_heridas = [x for x in st.session_state.get("fotos_heridas_db", []) if x.get("paciente") == paciente_sel]
    if fotos_heridas:
        st.divider()
        st.markdown("#### Linea de tiempo de heridas y lesiones")
        limite_fotos = seleccionar_limite_registros(
            "Fotos a mostrar",
            len(fotos_heridas),
            key=f"limite_fotos_heridas_{paciente_sel}",
            default=12,
            opciones=(6, 12, 20, 30),
        )
        with st.container(height=520):
            for foto in reversed(fotos_heridas[-limite_fotos:]):
                with st.container(border=True):
                    st.markdown(f"**{foto.get('fecha', 'S/D')}** | **{foto.get('firma', 'Sin firma')}**")
                    if foto.get("descripcion"):
                        st.caption(foto.get("descripcion"))
                    try:
                        st.image(base64.b64decode(foto.get("base64_foto", "")), use_container_width=True)
                    except Exception:
                        st.warning("No se pudo mostrar una foto registrada.")
