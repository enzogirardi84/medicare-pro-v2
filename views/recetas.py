import base64
import io
import os
from datetime import time as dt_time

import pandas as pd
import streamlit as st

from core.clinical_exports import build_prescription_pdf_bytes
from core.database import guardar_datos
from core.utils import (
    ahora,
    cargar_json_asset,
    firma_a_base64,
    format_horarios_receta,
    horarios_programados_desde_frecuencia,
    mostrar_dataframe_con_scroll,
    obtener_config_firma,
    obtener_horarios_receta,
    puede_accion,
    parse_horarios_programados,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
)

FPDF_DISPONIBLE = False
try:
    from fpdf import FPDF

    FPDF_DISPONIBLE = True
except ImportError:
    pass

CANVAS_DISPONIBLE = False
try:
    from streamlit_drawable_canvas import st_canvas

    CANVAS_DISPONIBLE = True
except ImportError:
    pass


def _archivo_a_base64(uploaded_file):
    if uploaded_file is None:
        return "", "", ""
    try:
        contenido = uploaded_file.getvalue()
        if not contenido:
            return "", "", ""
        return (
            base64.b64encode(contenido).decode("utf-8"),
            uploaded_file.name,
            uploaded_file.type or "application/octet-stream",
        )
    except Exception:
        return "", "", ""


def render_recetas(paciente_sel, mi_empresa, user, rol=None):
    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral.")
        return

    rol = rol or user.get("rol", "")
    puede_prescribir = puede_accion(rol, "recetas_prescribir")
    puede_cargar_papel = puede_accion(rol, "recetas_cargar_papel")
    puede_registrar_dosis = puede_accion(rol, "recetas_registrar_dosis")
    puede_cambiar_estado = puede_accion(rol, "recetas_cambiar_estado")

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Prescripcion y administracion de medicamentos</h2>
            <p class="mc-hero-text">La vista combina catalogo guiado, firma profesional y seguimiento de dosis para reducir errores de medicacion y dejar trazabilidad completa.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Catalogo de medicamentos</span>
                <span class="mc-chip">Firma medica</span>
                <span class="mc-chip">Registro de dosis</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if rol in {"Operativo", "Enfermeria"}:
        st.info(
            "El personal asistencial puede ver indicaciones activas, registrar dosis y cargar una indicacion medica en papel o PDF "
            "cuando el medico la deja firmada fuera del sistema."
        )

    try:
        vademecum_base = cargar_json_asset("vademecum.json")
    except Exception:
        vademecum_base = ["Medicamento 1", "Medicamento 2"]

    st.markdown(
        """
        <div class="mc-grid-3">
            <div class="mc-card"><h4>Menos errores</h4><p>Elegir del catalogo evita cargar nombres mal escritos o presentaciones confusas.</p></div>
            <div class="mc-card"><h4>Receta trazable</h4><p>La prescripcion queda con fecha, medico, matricula y firma digital cuando esta disponible.</p></div>
            <div class="mc-card"><h4>Control diario</h4><p>La sabana muestra rapido si cada dosis fue realizada o quedo pendiente.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if puede_prescribir:
        st.markdown("##### Nueva prescripcion medica")
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            med_vademecum = c1.selectbox("Medicamento", ["-- Seleccionar del vademecum --"] + vademecum_base)
            med_manual = c2.text_input("O escribir manualmente")
            col3, col4, col5 = st.columns([2, 2, 1])
            via = col3.selectbox(
                "Via de administracion",
                ["Via Oral", "Via Endovenosa", "Via Intramuscular", "Via Subcutanea", "Via Topica", "Via Inhalatoria", "Otra"],
            )
            frecuencia = col4.selectbox(
                "Frecuencia",
                [
                    "Cada 1 hora",
                    "Cada 2 horas",
                    "Cada 4 horas",
                    "Cada 6 horas",
                    "Cada 8 horas",
                    "Cada 12 horas",
                    "Cada 24 horas",
                    "Dosis unica",
                    "Segun necesidad",
                ],
            )
            dias = col5.number_input("Dias", min_value=1, max_value=90, value=7)
            hora_inicio = st.time_input("Hora inicial de administracion", value=dt_time(8, 0), key="hora_inicio_receta")
            horarios_sugeridos = horarios_programados_desde_frecuencia(
                frecuencia,
                hora_inicio.strftime("%H:%M"),
            )
            if horarios_sugeridos:
                st.caption(f"Horarios sugeridos para la guardia: {' | '.join(horarios_sugeridos)}")
            else:
                st.caption("Indicacion sin horario fijo. Se mostrara como dosis unica o a demanda segun la frecuencia.")
            col_m1, col_m2 = st.columns(2)
            medico_nombre = col_m1.text_input("Nombre del medico", value=user.get("nombre", ""))
            medico_matricula = col_m2.text_input("Matricula profesional")

            firma_canvas = None
            firma_subida = None
            if CANVAS_DISPONIBLE and st.checkbox("Cargar firma digital", value=False):
                firma_cfg = obtener_config_firma("receta")
                metodo_firma = st.radio(
                    "Metodo de firma medica",
                    ["Subir foto de la firma (recomendado en celulares viejos)", "Firmar en pantalla"],
                    horizontal=True,
                    key="metodo_firma_receta",
                )
                if metodo_firma.startswith("Subir"):
                    firma_subida = st.file_uploader(
                        "Subir imagen de la firma medica",
                        type=["png", "jpg", "jpeg"],
                        key="firma_upload_receta",
                    )
                else:
                    st.caption("Si el telefono va lento, vuelve a la opcion de subir foto.")
                    firma_canvas = st_canvas(
                        key="firma_receta_activa",
                        background_color="#ffffff",
                        height=firma_cfg["height"],
                        width=firma_cfg["width"],
                        drawing_mode="freedraw",
                        stroke_width=firma_cfg["stroke_width"],
                        stroke_color="#000000",
                        display_toolbar=firma_cfg["display_toolbar"],
                    )

            if st.button("Guardar prescripcion medica", use_container_width=True, type="primary"):
                med_final = med_manual.strip().title() if med_manual.strip() else med_vademecum
                if med_final and med_final != "-- Seleccionar del vademecum --":
                    if not medico_matricula.strip():
                        st.error("Debe ingresar la matricula del medico.")
                    else:
                        firma_b64 = firma_a_base64(
                            canvas_image_data=firma_canvas.image_data if firma_canvas is not None else None,
                            uploaded_file=firma_subida,
                        )

                        texto_receta = f"{med_final} | Via: {via} | {frecuencia} | Durante {dias} dias"
                        st.session_state["indicaciones_db"].append(
                            {
                                "paciente": paciente_sel,
                                "med": texto_receta,
                                "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                                "dias_duracion": dias,
                                "medico_nombre": medico_nombre.strip(),
                                "medico_matricula": medico_matricula.strip(),
                                "firma_b64": firma_b64,
                                "firmado_por": user["nombre"],
                                "estado_clinico": "Activa",
                                "estado_receta": "Activa",
                                "frecuencia": frecuencia,
                                "hora_inicio": hora_inicio.strftime("%H:%M"),
                                "horarios_programados": horarios_sugeridos,
                                "fecha_estado": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                                "profesional_estado": user["nombre"],
                                "matricula_estado": medico_matricula.strip(),
                                "origen_registro": "Prescripcion digital",
                                "empresa": mi_empresa,
                            }
                        )
                        registrar_auditoria_legal(
                            "Medicacion",
                            paciente_sel,
                            "Indicacion medica registrada",
                            medico_nombre.strip() or user.get("nombre", ""),
                            medico_matricula.strip(),
                            texto_receta,
                        )
                        guardar_datos()
                        st.success(f"Prescripcion de {med_final} guardada con firma medica.")
                        st.rerun()

    if puede_cargar_papel:
        st.markdown("##### Cargar indicacion medica en papel")
        with st.container(border=True):
            st.caption(
                "Usa esta opcion cuando el medico deja una indicacion firmada en papel o PDF y queres dejarla trazable en el sistema."
            )
            c_p1, c_p2 = st.columns(2)
            medico_papel = c_p1.text_input(
                "Medico que indica",
                key="medico_papel_nombre",
                value=user.get("nombre", "") if rol not in {"Operativo", "Enfermeria"} else "",
            )
            matricula_papel = c_p2.text_input("Matricula del medico", key="medico_papel_matricula")
            detalle_papel = st.text_area(
                "Resumen de la indicacion",
                key="detalle_papel_receta",
                placeholder="Ej: Ceftriaxona 1g EV cada 12 horas por 7 dias. Control de temperatura y signos vitales.",
            )
            c_p3, c_p4 = st.columns([1, 2])
            dias_papel = c_p3.number_input("Dias indicados", min_value=1, max_value=90, value=7, key="dias_papel_receta")
            horarios_papel_txt = c_p4.text_input(
                "Horarios programados (opcional)",
                key="horarios_papel_receta",
                placeholder="Ej: 08:00 | 16:00 | 22:00",
            )
            horarios_papel = parse_horarios_programados(horarios_papel_txt)
            if horarios_papel:
                st.caption(f"Quedaran visibles en la sabana diaria: {' | '.join(horarios_papel)}")
            adjunto_papel = st.file_uploader(
                "Subir orden medica en papel o PDF",
                type=["pdf", "png", "jpg", "jpeg"],
                key="adjunto_papel_receta",
            )
            if st.button("Guardar indicacion en papel", use_container_width=True, key="guardar_indicacion_papel"):
                if not medico_papel.strip() or not matricula_papel.strip():
                    st.error("Debe completar medico y matricula para dejar respaldo legal.")
                elif not detalle_papel.strip():
                    st.error("Debe resumir la indicacion medica para que se vea rapido en la guardia.")
                elif adjunto_papel is None:
                    st.error("Debe adjuntar la orden medica escaneada o fotografiada.")
                else:
                    adjunto_b64, adjunto_nombre, adjunto_tipo = _archivo_a_base64(adjunto_papel)
                    registro = {
                        "paciente": paciente_sel,
                        "med": detalle_papel.strip(),
                        "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                        "dias_duracion": dias_papel,
                        "medico_nombre": medico_papel.strip(),
                        "medico_matricula": matricula_papel.strip(),
                        "firma_b64": "",
                        "firmado_por": user["nombre"],
                        "estado_clinico": "Activa",
                        "estado_receta": "Activa",
                        "frecuencia": "",
                        "hora_inicio": horarios_papel[0] if horarios_papel else "",
                        "horarios_programados": horarios_papel,
                        "fecha_estado": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                        "profesional_estado": user["nombre"],
                        "matricula_estado": user.get("matricula", ""),
                        "origen_registro": "Indicacion medica en papel",
                        "adjunto_papel_b64": adjunto_b64,
                        "adjunto_papel_nombre": adjunto_nombre,
                        "adjunto_papel_tipo": adjunto_tipo,
                        "empresa": mi_empresa,
                    }
                    st.session_state["indicaciones_db"].append(registro)
                    registrar_auditoria_legal(
                        "Medicacion",
                        paciente_sel,
                        "Indicacion medica en papel cargada",
                        user.get("nombre", ""),
                        user.get("matricula", ""),
                        f"Medico: {medico_papel.strip()} | Matricula: {matricula_papel.strip()} | {detalle_papel.strip()}",
                    )
                    guardar_datos()
                    st.success("La indicacion medica en papel quedo guardada y disponible en el historial.")
                    st.rerun()

    st.divider()
    recs_todas = [r for r in st.session_state.get("indicaciones_db", []) if r.get("paciente") == paciente_sel]
    recs_activas = [r for r in recs_todas if r.get("estado_receta", "Activa") == "Activa"]

    if recs_activas:
        st.markdown("#### Administracion de hoy")
        fecha_hoy = ahora().strftime("%d/%m/%Y")
        admin_hoy = [
            a
            for a in st.session_state.get("administracion_med_db", [])
            if a.get("paciente") == paciente_sel and a.get("fecha") == fecha_hoy
        ]
        plan_dia = []
        sabana_resumen = []
        for r in recs_activas[:40]:
            partes = r["med"].split(" | ")
            nombre = partes[0].strip()
            via_texto = partes[1].replace("Via: ", "") if len(partes) > 1 else ""
            frecuencia_texto = r.get("frecuencia") or (partes[2] if len(partes) > 2 else "")
            horarios = obtener_horarios_receta(r)
            horarios_legibles = format_horarios_receta(r)
            sabana_resumen.append(
                {
                    "Medicamento": nombre,
                    "Via": via_texto or "S/D",
                    "Frecuencia": frecuencia_texto or "S/D",
                    "Horarios": horarios_legibles,
                    "Estado": r.get("estado_receta", "Activa"),
                }
            )

            if horarios:
                for horario in horarios:
                    admin_reg = next(
                        (
                            a
                            for a in admin_hoy
                            if a.get("med") == nombre
                            and (a.get("horario_programado") == horario or a.get("hora") == horario)
                        ),
                        None,
                    )
                    plan_dia.append(
                        {
                            "Hora": horario,
                            "Medicamento": nombre,
                            "Via": via_texto or "S/D",
                            "Frecuencia": frecuencia_texto or "S/D",
                            "Estado": admin_reg.get("estado", "Pendiente") if admin_reg else "Pendiente",
                            "Observacion": admin_reg.get("motivo", "") if admin_reg else "",
                            "Registrado por": admin_reg.get("firma", "") if admin_reg else "",
                            "Hora real": admin_reg.get("hora", "") if admin_reg else "",
                        }
                    )
            else:
                admin_reg = next((a for a in admin_hoy if a.get("med") == nombre), None)
                plan_dia.append(
                    {
                        "Hora": "A demanda",
                        "Medicamento": nombre,
                        "Via": via_texto or "S/D",
                        "Frecuencia": frecuencia_texto or "A demanda",
                        "Estado": admin_reg.get("estado", "Pendiente") if admin_reg else "Pendiente",
                        "Observacion": admin_reg.get("motivo", "") if admin_reg else "",
                        "Registrado por": admin_reg.get("firma", "") if admin_reg else "",
                        "Hora real": admin_reg.get("hora", "") if admin_reg else "",
                    }
                )

        st.caption("Plan de administracion del dia")
        mostrar_dataframe_con_scroll(pd.DataFrame(plan_dia), height=360)

        with st.expander("Ver sabana resumida de medicacion"):
            mostrar_dataframe_con_scroll(pd.DataFrame(sabana_resumen), height=280)

        if puede_registrar_dosis:
            with st.form("form_registro_dosis", clear_on_submit=True):
                recetas_map = {
                    f"{r['med'].split(' |')[0].strip()} | {format_horarios_receta(r)}": r
                    for r in recs_activas
                }
                c_med, c_hora = st.columns([2, 1])
                receta_label = c_med.selectbox("Medicacion a registrar", list(recetas_map.keys()))
                receta_actual = recetas_map[receta_label]
                horarios_receta = obtener_horarios_receta(receta_actual)
                opciones_hora = horarios_receta or [f"{i:02d}:00" for i in range(24)]
                if "A demanda" not in opciones_hora and not horarios_receta:
                    pass
                hora_actual_str = f"{ahora().hour:02d}:00"
                idx_hora = opciones_hora.index(hora_actual_str) if hora_actual_str in opciones_hora else 0
                hora_sel = c_hora.selectbox(
                    "Horario programado",
                    opciones_hora if opciones_hora else ["A demanda"],
                    index=idx_hora if opciones_hora else 0,
                )
                estado_sel = st.radio("Estado", ["Realizada", "No realizada / Suspendida"], horizontal=True)
                justificacion = st.text_input("Justificacion clinica")
                if st.form_submit_button("Guardar registro", use_container_width=True):
                    if "No realizada" in estado_sel and not justificacion.strip():
                        st.error("Es obligatorio justificar por que no se administro la dosis.")
                    else:
                        nombre_med = receta_actual["med"].split(" |")[0].strip()
                        st.session_state["administracion_med_db"] = [
                            a
                            for a in st.session_state.get("administracion_med_db", [])
                            if not (
                                a.get("paciente") == paciente_sel
                                and a.get("fecha") == fecha_hoy
                                and a.get("med") == nombre_med
                                and (a.get("horario_programado") == hora_sel or a.get("hora") == hora_sel)
                            )
                        ]
                        st.session_state["administracion_med_db"].append(
                            {
                                "paciente": paciente_sel,
                                "med": nombre_med,
                                "fecha": fecha_hoy,
                                "hora": ahora().strftime("%H:%M"),
                                "horario_programado": hora_sel,
                                "estado": estado_sel,
                                "motivo": justificacion.strip() if "No realizada" in estado_sel else "",
                                "firma": user["nombre"],
                                "empresa": mi_empresa,
                            }
                        )
                        registrar_auditoria_legal(
                            "Medicacion",
                            paciente_sel,
                            "Registro de administracion",
                            user.get("nombre", ""),
                            user.get("matricula", ""),
                            f"{nombre_med} | Horario: {hora_sel} | Estado: {estado_sel}",
                        )
                        guardar_datos()
                        st.success(f"Registro guardado para el horario {hora_sel}.")
                        st.rerun()
        else:
            st.caption("El registro de administracion queda deshabilitado para este rol.")

        st.divider()
        if puede_cambiar_estado:
            c_ed1, c_ed2 = st.columns([3, 2])
            opciones_recetas = [f"[{r.get('fecha', '')}] {r.get('med', '')}" for r in recs_activas]
            receta_seleccionada = c_ed1.selectbox("Seleccionar indicacion", opciones_recetas)
            accion_receta = c_ed2.selectbox("Accion", ["Suspender / Anular", "Editar indicacion"])
            nuevo_texto_receta = ""
            motivo_cambio = st.text_input("Motivo medico / legal del cambio", key="motivo_cambio_receta")
            if accion_receta == "Editar indicacion" and receta_seleccionada:
                nuevo_texto_receta = st.text_input(
                    "Modificar detalle",
                    value=receta_seleccionada.split("] ", 1)[1] if "] " in receta_seleccionada else receta_seleccionada,
                )
            if st.button("Aplicar cambios", use_container_width=True):
                for r in st.session_state["indicaciones_db"]:
                    if r["paciente"] == paciente_sel and f"[{r.get('fecha', '')}] {r.get('med', '')}" == receta_seleccionada:
                        if accion_receta == "Suspender / Anular":
                            r["estado_receta"] = "Suspendida"
                            r["estado_clinico"] = "Suspendida"
                            r["fecha_suspension"] = ahora().strftime("%d/%m/%Y %H:%M:%S")
                            r["fecha_estado"] = r["fecha_suspension"]
                            r["profesional_estado"] = user["nombre"]
                            r["matricula_estado"] = user.get("matricula", "")
                            r["motivo_estado"] = motivo_cambio.strip()
                            registrar_auditoria_legal(
                                "Medicacion",
                                paciente_sel,
                                "Indicacion suspendida",
                                user.get("nombre", ""),
                                user.get("matricula", ""),
                                f"{r.get('med', '')} | Motivo: {motivo_cambio.strip()}",
                            )
                        elif accion_receta == "Editar indicacion" and nuevo_texto_receta:
                            r["estado_receta"] = "Modificada"
                            r["estado_clinico"] = "Modificada"
                            r["fecha_suspension"] = ahora().strftime("%d/%m/%Y %H:%M:%S")
                            r["fecha_estado"] = r["fecha_suspension"]
                            r["profesional_estado"] = user["nombre"]
                            r["matricula_estado"] = user.get("matricula", "")
                            r["motivo_estado"] = motivo_cambio.strip()
                            st.session_state["indicaciones_db"].append(
                                {
                                    "paciente": paciente_sel,
                                    "med": nuevo_texto_receta,
                                    "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                                    "dias_duracion": r.get("dias_duracion", 7),
                                    "medico_nombre": r.get("medico_nombre", ""),
                                    "medico_matricula": r.get("medico_matricula", ""),
                                    "firma_b64": r.get("firma_b64", ""),
                                    "firmado_por": user["nombre"],
                                    "estado_clinico": "Activa",
                                    "estado_receta": "Activa",
                                    "frecuencia": r.get("frecuencia", ""),
                                    "hora_inicio": r.get("hora_inicio", ""),
                                    "horarios_programados": r.get("horarios_programados", []),
                                    "fecha_estado": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                                    "profesional_estado": user["nombre"],
                                    "matricula_estado": user.get("matricula", ""),
                                    "motivo_estado": f"Reemplaza indicacion previa. Motivo: {motivo_cambio.strip()}".strip(),
                                    "origen_registro": "Prescripcion digital",
                                    "empresa": r.get("empresa", mi_empresa),
                                }
                            )
                            registrar_auditoria_legal(
                                "Medicacion",
                                paciente_sel,
                                "Indicacion modificada",
                                user.get("nombre", ""),
                                user.get("matricula", ""),
                                f"Anterior: {r.get('med', '')} | Nueva: {nuevo_texto_receta} | Motivo: {motivo_cambio.strip()}",
                            )
                        break
                guardar_datos()
                st.rerun()
        else:
            st.caption(
                "La suspension o modificacion de indicaciones queda reservada a medico, coordinacion o administracion con acceso total."
            )
    else:
        st.info("Aun no hay medicacion activa para este paciente.")

    st.divider()
    if recs_todas:
        st.markdown("#### Historial completo de prescripciones")
        limite_hist = seleccionar_limite_registros(
            "Prescripciones a mostrar",
            len(recs_todas),
            key=f"limite_recetas_hist_{paciente_sel}",
            default=30,
        )

        with st.container(height=450):
            for idx, r in enumerate(reversed(recs_todas[-limite_hist:])):
                with st.container(border=True):
                    c_info, c_btn = st.columns([3, 1])
                    estado_actual = r.get("estado_receta", "Activa")
                    c_info.markdown(f"**{r.get('fecha', '-')}**")
                    c_info.markdown(
                        f"**Indicado por:** {r.get('medico_nombre', '-')} | **Matricula:** {r.get('medico_matricula', '-')}"
                    )
                    if r.get("origen_registro"):
                        c_info.caption(f"Origen: {r.get('origen_registro')}")
                    c_info.markdown(f"*{r.get('med', '')}*")
                    c_info.caption(f"Horarios: {format_horarios_receta(r)}")
                    if r.get("firma_b64"):
                        try:
                            c_info.image(base64.b64decode(r["firma_b64"]), caption="Firma medica registrada", width=200)
                        except Exception:
                            pass
                    if r.get("adjunto_papel_b64"):
                        try:
                            c_btn.download_button(
                                "Descargar orden adjunta",
                                data=base64.b64decode(r["adjunto_papel_b64"]),
                                file_name=r.get("adjunto_papel_nombre", "indicacion_medica.pdf"),
                                mime=r.get("adjunto_papel_tipo", "application/octet-stream"),
                                key=f"adj_papel_btn_{idx}",
                                use_container_width=True,
                            )
                        except Exception:
                            c_info.caption("No se pudo preparar el adjunto cargado.")
                    if estado_actual != "Activa":
                        c_info.error(
                            f"Estado: {estado_actual.upper()} | Fecha: {r.get('fecha_suspension', 'S/D')} | "
                            f"Profesional: {r.get('profesional_estado', 'S/D')}"
                        )
                        if r.get("motivo_estado"):
                            c_info.caption(f"Motivo: {r.get('motivo_estado')}")
                    if FPDF_DISPONIBLE and st.checkbox("PDF", key=f"pdf_rec_{idx}", value=False):
                        pdf_bytes = build_prescription_pdf_bytes(
                            st.session_state,
                            paciente_sel,
                            mi_empresa,
                            r,
                            {"nombre": r.get("medico_nombre", user.get("nombre", "")), "matricula": r.get("medico_matricula", "")},
                        )
                        estado_arch = (r.get("estado_receta") or "Activa").replace(" ", "_")
                        nombre_arch = (
                            f"Receta_Legal_{paciente_sel.split(' - ')[0].replace(' ', '_')}_"
                            f"{r.get('fecha', '')[:10].replace('/','')}_{estado_arch}.pdf"
                        )
                        c_btn.download_button(
                            "Descargar PDF legal",
                            data=pdf_bytes,
                            file_name=nombre_arch,
                            mime="application/pdf",
                            key=f"pdf_rec_btn_{idx}",
                            use_container_width=True,
                        )
