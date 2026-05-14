"""Tabs UI de emergencias. Extraído de views/emergencias.py."""
import base64
from uuid import uuid4

import streamlit as st

from core.alert_toasts import queue_toast
from core.app_logging import log_event
from core.clinical_exports import build_emergency_pdf_bytes
from core.database import guardar_datos
from core.db_sql import insert_emergencia
from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
from core.utils import (
    ahora,
    mapa_detalles_pacientes,
    mostrar_dataframe_con_scroll,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
)
from core.view_helpers import bloque_estado_vacio, lista_plegable
from views._emergencias_data import EVENTO_CATEGORIAS, _badge_html, _firma_a_b64, _triage_meta

CANVAS_DISPONIBLE = False
try:
    from streamlit_drawable_canvas import st_canvas
    CANVAS_DISPONIBLE = True
except ImportError:
    pass  # Intencional: canvas es opcional para firmas


def _render_tab_registrar(paciente_sel, mi_empresa, user, detalles, es_movil):
    """Tab: Registrar evento crítico."""
    fecha_actual = ahora()
    _partes_em = paciente_sel.split(" - ")
    _dni_em = _partes_em[1].strip() if len(_partes_em) > 1 else ""

    with st.container(border=True):
        if es_movil:
            triage_grado = st.selectbox(
                "Triage",
                ["Grado 1 - Rojo", "Grado 2 - Amarillo", "Grado 3 - Verde"],
                index=1,
                key="em_triage",
            )
            triage_info = _triage_meta(triage_grado)
            codigo_alerta = triage_info["codigo"]
            categoria_evento = st.selectbox("Categoria", list(EVENTO_CATEGORIAS.keys()), key="em_cat")
            patologias_categoria = EVENTO_CATEGORIAS.get(categoria_evento, ["Evento no clasificado"])
            tipo_evento = st.selectbox("Tipo / motivo presuntivo", patologias_categoria, key="em_tipo")
        else:
            c1, c2, c3 = st.columns([1, 2, 2])
            triage_grado = c1.selectbox(
                "Triage",
                ["Grado 1 - Rojo", "Grado 2 - Amarillo", "Grado 3 - Verde"],
                index=1,
                key="em_triage",
            )
            triage_info = _triage_meta(triage_grado)
            codigo_alerta = triage_info["codigo"]
            categoria_evento = c2.selectbox("Categoria", list(EVENTO_CATEGORIAS.keys()), key="em_cat")
            patologias_categoria = EVENTO_CATEGORIAS.get(categoria_evento, ["Evento no clasificado"])
            tipo_evento = c3.selectbox("Tipo / motivo presuntivo", patologias_categoria, key="em_tipo")

        motivo = st.text_area("Motivo principal", height=70, placeholder="Descripcion breve del cuadro", key="em_motivo")

        if es_movil:
            v1, v2 = st.columns(2)
            presion = v1.text_input("TA", placeholder="120/80", key="em_ta")
            fc = v2.text_input("FC", placeholder="78", key="em_fc")
            v3, v4 = st.columns(2)
            saturacion = v3.text_input("SaO2", placeholder="98%", key="em_sat")
            temperatura = v4.text_input("Temp", placeholder="36.5", key="em_temp")
        else:
            v1, v2, v3, v4 = st.columns(4)
            presion = v1.text_input("TA", placeholder="120/80", key="em_ta")
            fc = v2.text_input("FC", placeholder="78", key="em_fc")
            saturacion = v3.text_input("SaO2", placeholder="98%", key="em_sat")
            temperatura = v4.text_input("Temp", placeholder="36.5", key="em_temp")

        ambulancia_solicitada = st.checkbox(
            "Ambulancia",
            value=triage_info["prioridad"] in {"Alta", "Critica"},
            key="em_amb",
        )
        if es_movil:
            movil = st.text_input("Movil / empresa", placeholder="Emerger / SAME", key="em_movil")
            destino = st.text_input("Destino", placeholder="Guardia / hospital", key="em_dest")
        else:
            a2, a3 = st.columns(2)
            movil = a2.text_input("Movil / empresa", placeholder="Emerger / SAME", key="em_movil")
            destino = a3.text_input("Destino", placeholder="Guardia / hospital", key="em_dest")

        if es_movil:
            profesional = st.text_input("Profesional a cargo", value=user.get("nombre", ""), key="em_prof")
            matricula = st.text_input("Matricula", value=user.get("matricula", ""), key="em_mat")
        else:
            p1, p2 = st.columns(2)
            profesional = p1.text_input("Profesional a cargo", value=user.get("nombre", ""), key="em_prof")
            matricula = p2.text_input("Matricula", value=user.get("matricula", ""), key="em_mat")

        with st.expander("Mas datos (opcional)"):
            if es_movil:
                d1, d2 = st.columns(2)
                glucemia = d1.text_input("Glucemia", placeholder="110 mg/dl", key="em_gluc")
                dolor = d2.selectbox("Dolor EVA", [str(x) for x in range(11)], index=0, key="em_dolor")
                conciencia = st.selectbox("Conciencia", ["Alerta", "Somnoliento", "Confuso", "No responde"], key="em_conc")
                e1, e2 = st.columns(2)
                tipo_traslado = e1.selectbox("Tipo traslado", ["Sin traslado confirmado", "Traslado asistencial", "Derivacion a guardia", "Traslado interhospitalario", "Alta complejidad / UTI movil", "Retorno a domicilio"], key="em_tras")
                hora_solicitud = e2.text_input("Hora solicitud", value=fecha_actual.strftime("%H:%M"), key="em_hsol")
                hora_arribo = st.text_input("Hora arribo", placeholder="HH:MM", key="em_harr")
            else:
                d1, d2, d3 = st.columns(3)
                glucemia = d1.text_input("Glucemia", placeholder="110 mg/dl", key="em_gluc")
                dolor = d2.selectbox("Dolor EVA", [str(x) for x in range(11)], index=0, key="em_dolor")
                conciencia = d3.selectbox("Conciencia", ["Alerta", "Somnoliento", "Confuso", "No responde"], key="em_conc")
                e1, e2, e3 = st.columns(3)
                tipo_traslado = e1.selectbox("Tipo traslado", ["Sin traslado confirmado", "Traslado asistencial", "Derivacion a guardia", "Traslado interhospitalario", "Alta complejidad / UTI movil", "Retorno a domicilio"], key="em_tras")
                hora_solicitud = e2.text_input("Hora solicitud", value=fecha_actual.strftime("%H:%M"), key="em_hsol")
                hora_arribo = e3.text_input("Hora arribo", placeholder="HH:MM", key="em_harr")
            if es_movil:
                hora_salida = st.text_input("Hora salida", placeholder="HH:MM", key="em_hsal")
                receptor = st.text_input("Receptor / institucion", key="em_rec")
            else:
                f1, f2 = st.columns(2)
                hora_salida = f1.text_input("Hora salida", placeholder="HH:MM", key="em_hsal")
                receptor = f2.text_input("Receptor / institucion", key="em_rec")
            familiar_notificado = st.text_input("Familiar notificado", key="em_fam")
            fecha_evento = st.date_input("Fecha (si distinta a hoy)", value=fecha_actual.date(), key="em_fecha")
            hora_evento = st.time_input("Hora inicio (si distinta)", value=fecha_actual.time().replace(microsecond=0), key="em_hora")
            procedimientos = st.text_area("Procedimientos realizados", height=70, key="em_proc")
            medicacion_administrada = st.text_area("Medicacion administrada", height=70, key="em_meds")
            respuesta = st.text_area("Respuesta del paciente", height=60, key="em_resp")
            observaciones_legales = st.text_area("Observaciones legales", height=60, key="em_obs_leg")
            observaciones = st.text_area("Observaciones clinicas", height=60, key="em_obs")
            direccion_evento = st.text_input("Domicilio del evento", value=detalles.get("direccion", ""), key="em_dir")
            firma_canvas = None
            if CANVAS_DISPONIBLE:
                st.caption("Firma digital del profesional")
                firma_canvas = st_canvas(
                    key="firma_emergencias",
                    background_color="#ffffff",
                    height=90 if es_movil else 120,
                    drawing_mode="freedraw",
                    stroke_width=3,
                    stroke_color="#000000",
                    display_toolbar=True,
                )

        if "em_tras" not in st.session_state:
            tipo_traslado = "Sin traslado confirmado"
        if "em_fecha" not in st.session_state:
            fecha_evento = fecha_actual.date()
        if "em_hora" not in st.session_state:
            hora_evento = fecha_actual.time().replace(microsecond=0)

        if st.button("GUARDAR EVENTO CRITICO", width='stretch', type="primary", key="em_guardar"):
            if not motivo.strip():
                st.error("Debes indicar el motivo principal del evento.")
            elif not profesional.strip() or not matricula.strip():
                st.error("Debes registrar profesional y matricula para dejar respaldo legal.")
            else:
                fecha_str = ahora().strftime("%d/%m/%Y %H:%M:%S")

                tipo_traslado = st.session_state.get("em_tras", "Sin traslado confirmado")
                hora_solicitud = st.session_state.get("em_hsol", fecha_actual.strftime("%H:%M"))
                hora_arribo = st.session_state.get("em_harr", "")
                hora_salida = st.session_state.get("em_hsal", "")
                receptor = st.session_state.get("em_rec", "")
                familiar_notificado = st.session_state.get("em_fam", "")
                fecha_evento = st.session_state.get("em_fecha", fecha_actual.date())
                hora_evento = st.session_state.get("em_hora", fecha_actual.time().replace(microsecond=0))
                glucemia = st.session_state.get("em_gluc", "")
                dolor = st.session_state.get("em_dolor", "0")
                conciencia = st.session_state.get("em_conc", "Alerta")
                procedimientos = st.session_state.get("em_proc", "")
                medicacion_administrada = st.session_state.get("em_meds", "")
                respuesta = st.session_state.get("em_resp", "")
                observaciones_legales = st.session_state.get("em_obs_leg", "")
                observaciones = st.session_state.get("em_obs", "")
                direccion_evento = st.session_state.get("em_dir", detalles.get("direccion", ""))
                firma_canvas = None

                try:
                    empresa_uuid = _obtener_uuid_empresa(mi_empresa)
                    paciente_uuid = _obtener_uuid_paciente(_dni_em, empresa_uuid) if _dni_em and empresa_uuid else None
                    if paciente_uuid and empresa_uuid:
                        datos_sql = {
                            "empresa_id": empresa_uuid,
                            "paciente_id": paciente_uuid,
                            "fecha_llamado": ahora().isoformat(),
                            "motivo": motivo.strip(),
                            "prioridad": triage_info["prioridad"],
                            "estado": "Pendiente",
                            "resolucion": f"Destino: {destino.strip()} | Receptor: {receptor.strip()} | Procedimientos: {procedimientos.strip()} | Medicación: {medicacion_administrada.strip()} | Respuesta: {respuesta.strip()}",
                            "recursos_asignados": f"Móvil: {movil.strip()} | Profesional: {profesional.strip()} | Matrícula: {matricula.strip()}" if ambulancia_solicitada else f"Profesional: {profesional.strip()} | Matrícula: {matricula.strip()}",
                        }
                        insert_emergencia(datos_sql)
                        log_event("emergencia_sql_insert", f"Paciente: {paciente_uuid}")
                except Exception as e:
                    log_event("error_emergencia_sql", str(e))

                nuevo = {
                    "id": str(uuid4()),
                    "paciente": paciente_sel,
                    "empresa": mi_empresa,
                    "fecha_evento": fecha_evento.strftime("%d/%m/%Y"),
                    "hora_evento": hora_evento.strftime("%H:%M"),
                    "categoria_evento": categoria_evento,
                    "tipo_evento": tipo_evento,
                    "tipo_traslado": tipo_traslado,
                    "triage_grado": triage_grado,
                    "prioridad": triage_info["prioridad"],
                    "codigo_alerta": codigo_alerta,
                    "motivo": motivo.strip(),
                    "direccion_evento": direccion_evento.strip(),
                    "presion_arterial": presion.strip(),
                    "fc": fc.strip(),
                    "saturacion": saturacion.strip(),
                    "temperatura": temperatura.strip(),
                    "glucemia": glucemia.strip(),
                    "dolor": dolor,
                    "conciencia": conciencia,
                    "observaciones": observaciones.strip(),
                    "ambulancia_solicitada": ambulancia_solicitada,
                    "movil": movil.strip(),
                    "hora_solicitud": hora_solicitud.strip(),
                    "hora_arribo": hora_arribo.strip(),
                    "hora_salida": hora_salida.strip(),
                    "destino": destino.strip(),
                    "receptor": receptor.strip(),
                    "familiar_notificado": familiar_notificado.strip(),
                    "procedimientos": procedimientos.strip(),
                    "medicacion_administrada": medicacion_administrada.strip(),
                    "respuesta": respuesta.strip(),
                    "observaciones_legales": observaciones_legales.strip(),
                    "profesional": profesional.strip(),
                    "matricula": matricula.strip(),
                    "firma_b64": _firma_a_b64(firma_canvas),
                    "creado_en": fecha_str,
                    "creado_por": user.get("nombre", ""),
                }
                if "emergencias_db" not in st.session_state:
                    st.session_state["emergencias_db"] = []
                st.session_state["emergencias_db"].append(nuevo)
                from core.database import _trim_db_list
                _trim_db_list("emergencias_db", 500)

                registrar_auditoria_legal(
                    "Emergencia",
                    paciente_sel,
                    "Evento critico registrado",
                    profesional.strip(),
                    matricula.strip(),
                    f"{categoria_evento} | {tipo_evento} | {triage_grado} | Traslado: {tipo_traslado}",
                )
                guardar_datos(spinner=True)
                queue_toast("Evento de emergencia guardado con trazabilidad legal.")
                st.rerun()


def _render_tab_panel(paciente_sel, detalles, eventos, es_movil):
    """Tab: Panel operativo."""
    st.markdown("### Panel operativo del paciente")
    with st.container(border=True):
        st.markdown(
            f"""
            <div class="mc-note">
                <strong>Paciente:</strong> {paciente_sel}<br>
                <strong>Domicilio:</strong> {detalles.get("direccion", "S/D")}<br>
                <strong>Telefono:</strong> {detalles.get("telefono", "S/D")}<br>
                <strong>Alergias:</strong> {detalles.get("alergias", "Sin datos")}
            </div>
            """,
            unsafe_allow_html=True,
        )

    recientes = list(reversed(eventos[-6:]))
    if not recientes:
        bloque_estado_vacio(
            "Sin eventos de emergencia",
            "Todavía no hay eventos de emergencia o ambulancia registrados para este paciente.",
            sugerencia="Completá el formulario de evento arriba para el primer registro.",
        )
    else:
        altura_recientes = None if es_movil and len(recientes) <= 3 else (280 if es_movil else 420)
        with lista_plegable("Eventos recientes (panel operativo)", count=len(recientes), expanded=False, height=altura_recientes):
            for evento in recientes:
                titulo = f"{evento.get('fecha_evento', '')} {evento.get('hora_evento', '')} | {evento.get('tipo_evento', '')}"
                with st.container(border=True):
                    badges = [
                        _badge_html(evento.get("triage_grado", "S/D"), _triage_meta(evento.get("triage_grado", "")).get("clase", "")),
                        _badge_html(evento.get("prioridad", "S/D"), ""),
                        _badge_html("Ambulancia" if evento.get("ambulancia_solicitada") else "Sin movil", ""),
                    ]
                    if es_movil:
                        st.markdown(f"#### {titulo}")
                        st.markdown(" ".join(badges), unsafe_allow_html=True)
                        st.markdown(evento.get("motivo", ""))
                        st.caption(
                            f"Categoria: {evento.get('categoria_evento', 'S/D')} | Profesional: {evento.get('profesional', 'S/D')} | Matricula: {evento.get('matricula', 'S/D')} | Destino: {evento.get('destino', 'S/D')} | Traslado: {evento.get('tipo_traslado', 'S/D')}"
                        )
                        if evento.get("firma_b64"):
                            try:
                                st.image(base64.b64decode(evento["firma_b64"]), caption="Firma profesional", width=160)
                            except Exception as e:
                                log_event('emergencias_error', f'Error: {e}')
                    else:
                        col_info, col_badges = st.columns([4, 2])
                        col_info.markdown(f"#### {titulo}")
                        col_info.markdown(evento.get("motivo", ""))
                        col_badges.markdown(" ".join(badges), unsafe_allow_html=True)
                        col_info.caption(
                            f"Categoria: {evento.get('categoria_evento', 'S/D')} | Profesional: {evento.get('profesional', 'S/D')} | Matricula: {evento.get('matricula', 'S/D')} | Destino: {evento.get('destino', 'S/D')} | Traslado: {evento.get('tipo_traslado', 'S/D')}"
                        )
                        if evento.get("firma_b64"):
                            try:
                                col_badges.image(base64.b64decode(evento["firma_b64"]), caption="Firma profesional", width=180)
                            except Exception as e:
                                log_event('emergencias_error', f'Error: {e}')


def _render_tab_historial(paciente_sel, mi_empresa, eventos, es_movil):
    """Tab: Historial y PDF."""
    st.markdown("### Historial, tiempos y PDF")
    if not eventos:
        bloque_estado_vacio(
            "Nada para exportar",
            "No hay eventos registrados para armar tabla o PDF.",
            sugerencia="Registrá al menos un evento en la pestaña correspondiente.",
        )
        return

    limite = seleccionar_limite_registros(
        "Eventos a mostrar",
        len(eventos),
        key="emergencias_historial_limite",
        default=20,
        opciones=(5, 10, 20, 30, 50, 100, 200, 500),
    )

    registros = list(reversed(eventos[-limite:]))
    import pandas as pd
    resumen_df = pd.DataFrame(
        [
            {
                "Fecha": f"{x.get('fecha_evento', '')} {x.get('hora_evento', '')}",
                "Categoria": x.get("categoria_evento", ""),
                "Tipo": x.get("tipo_evento", ""),
                "Triage": x.get("triage_grado", ""),
                "Prioridad": x.get("prioridad", ""),
                "Traslado": x.get("tipo_traslado", ""),
                "Movil": x.get("movil", ""),
                "Destino": x.get("destino", ""),
                "Profesional": x.get("profesional", ""),
            }
            for x in registros
        ]
    )
    altura_resumen = None if es_movil and len(registros) <= 4 else (280 if es_movil else 400)
    with lista_plegable("Tabla resumen de eventos", count=len(registros), expanded=False, height=altura_resumen):
        mostrar_dataframe_con_scroll(resumen_df, height=220 if es_movil else 360)

    altura_detalle = None if es_movil and len(registros) <= 3 else (320 if es_movil else 520)
    with lista_plegable("Detalle y PDF por evento", count=len(registros), expanded=False, height=altura_detalle):
        for idx, evento in enumerate(registros):
            with st.container(border=True):
                if es_movil:
                    st.markdown(
                        f"**{evento.get('fecha_evento', '')} {evento.get('hora_evento', '')}** | {evento.get('tipo_evento', '')}"
                    )
                    st.caption(
                        f"Categoria: {evento.get('categoria_evento', 'S/D')} | Triage: {evento.get('triage_grado', 'S/D')} | Prioridad: {evento.get('prioridad', 'S/D')} | Traslado: {evento.get('tipo_traslado', 'S/D')} | Profesional: {evento.get('profesional', 'S/D')}"
                    )
                    st.markdown(evento.get("motivo", ""))
                    if evento.get("ambulancia_solicitada"):
                        st.info(
                            f"Movil: {evento.get('movil', 'S/D')} | Solicitud: {evento.get('hora_solicitud', 'S/D')} | "
                            f"Arribo: {evento.get('hora_arribo', 'S/D')} | Destino: {evento.get('destino', 'S/D')}"
                        )
                else:
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(
                        f"**{evento.get('fecha_evento', '')} {evento.get('hora_evento', '')}** | {evento.get('tipo_evento', '')}"
                    )
                    c1.caption(
                        f"Categoria: {evento.get('categoria_evento', 'S/D')} | Triage: {evento.get('triage_grado', 'S/D')} | Prioridad: {evento.get('prioridad', 'S/D')} | Traslado: {evento.get('tipo_traslado', 'S/D')} | Profesional: {evento.get('profesional', 'S/D')}"
                    )
                    c1.markdown(evento.get("motivo", ""))
                    if evento.get("ambulancia_solicitada"):
                        c1.info(
                            f"Movil: {evento.get('movil', 'S/D')} | Solicitud: {evento.get('hora_solicitud', 'S/D')} | "
                            f"Arribo: {evento.get('hora_arribo', 'S/D')} | Destino: {evento.get('destino', 'S/D')}"
                        )
                pdf_bytes = build_emergency_pdf_bytes(
                    st.session_state,
                    paciente_sel,
                    mi_empresa,
                    evento,
                    {"nombre": evento.get("profesional", ""), "matricula": evento.get("matricula", "")},
                )
                nombre_arch = (
                    f"Emergencia_{paciente_sel.split(' - ')[0].replace(' ', '_')}_"
                    f"{evento.get('fecha_evento', '').replace('/','')}_{idx + 1}.pdf"
                )
                if es_movil:
                    st.download_button(
                        "Descargar PDF",
                        data=pdf_bytes,
                        file_name=nombre_arch,
                        mime="application/pdf",
                        width='stretch',
                        key=f"pdf_emerg_{idx}",
                    )
                else:
                    c2.download_button(
                        "Descargar PDF",
                        data=pdf_bytes,
                        file_name=nombre_arch,
                        mime="application/pdf",
                        width='stretch',
                        key=f"pdf_emerg_{idx}",
                    )
