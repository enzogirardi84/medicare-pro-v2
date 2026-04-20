from core.alert_toasts import queue_toast
import io
import os
from datetime import time as dt_time
from html import escape

import streamlit as st
import pandas as pd

from core.anticolapso import anticolapso_activo
from core.clinical_exports import build_prescription_pdf_bytes
from core.database import guardar_datos
from core.utils import (
    ahora,
    calcular_velocidad_ml_h,
    cargar_json_asset,
    firma_a_base64,
    format_horarios_receta,
    generar_plan_escalonado_ml_h,
    horarios_programados_desde_frecuencia,
    mostrar_dataframe_con_scroll,
    obtener_config_firma,
    obtener_horarios_receta,
    puede_accion,
    parse_horarios_programados,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
)
from views._recetas_utils import (
    FPDF_DISPONIBLE,
    CANVAS_DISPONIBLE,
    render_tabla_clinica as _render_tabla_clinica,
    render_dataframe_filas_tarjetas as _render_dataframe_filas_tarjetas,
    render_plan_hidratacion_preview as _render_plan_hidratacion_preview,
    archivo_a_base64 as _archivo_a_base64,
    estado_icono as _estado_icono,
    estado_legible as _estado_legible,
    extraer_nombre_medicacion as _extraer_nombre_medicacion,
    resumen_plan_hidratacion as _resumen_plan_hidratacion,
    detalle_horario_infusion as _detalle_horario_infusion,
    nombre_usuario as _nombre_usuario,
    firma_trazabilidad_admin as _firma_trazabilidad_admin,
    parse_hora_hhmm as _parse_hora_hhmm,
    hora_real_para_registro as _hora_real_para_registro,
    orden_horario_programado as _orden_horario_programado,
    texto_corto as _texto_corto,
    etiqueta_receta as _etiqueta_receta,
)
from views._recetas_mar import (
    registrar_administracion_dosis as _registrar_administracion_dosis,
    guardar_administracion_medicacion as _guardar_administracion_medicacion,
    construir_matriz_registro_24h as _construir_matriz_registro_24h,
    tabla_guardia_operativa as _tabla_guardia_operativa,
    tabla_guardia_detallada as _tabla_guardia_detallada,
    render_cortina_mar_hospitalaria as _render_cortina_mar_hospitalaria,
    render_bloque_cortina_medicacion as _render_bloque_cortina_medicacion,
    render_sabana_compacta as _render_sabana_compacta,
    render_marco_clinico_cortina as _render_marco_clinico_cortina,
)
from views._recetas_indicaciones import (
    construir_texto_indicacion as _construir_texto_indicacion,
    resumen_medicacion_activa as _resumen_medicacion_activa,
)



def render_recetas(paciente_sel, mi_empresa, user, rol=None):
    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral.")
        return

    from core.ui_liviano import headers_sugieren_equipo_liviano

    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
    rol = rol or user.get("rol", "")
    nombre_usuario = _nombre_usuario(user)
    puede_prescribir = puede_accion(rol, "recetas_prescribir")
    puede_cargar_papel = puede_accion(rol, "recetas_cargar_papel")
    puede_registrar_dosis = puede_accion(rol, "recetas_registrar_dosis")
    puede_cambiar_estado = puede_accion(rol, "recetas_cambiar_estado")

    st.markdown("## Recetas y administración")
    st.caption(f"Profesional en sesión: **{nombre_usuario}**")

    _resumen_medicacion_activa(paciente_sel, mi_empresa)

    try:
        vademecum_base = cargar_json_asset("vademecum.json")
    except Exception:
        vademecum_base = ["Medicamento 1", "Medicamento 2"]

    if puede_prescribir:
        st.subheader("Nueva prescripción médica")
        with st.container(border=True):
            tipo_indicacion = st.radio(
                "Tipo de indicacion",
                ["Medicacion", "Infusion / hidratacion"],
                horizontal=True,
                key="tipo_indicacion_receta",
            )

            med_vademecum = "-- Seleccionar del vademecum --"
            med_manual = ""
            solucion = ""
            volumen_ml = 0
            velocidad_ml_h = None
            alternar_con = ""
            detalle_infusion = ""
            plan_hidratacion = []
            frecuencia = ""

            if tipo_indicacion == "Medicacion":
                if es_movil:
                    med_vademecum = st.selectbox("Medicamento", ["-- Seleccionar del vademecum --"] + vademecum_base)
                    med_manual = st.text_input("O escribir manualmente")
                    via = st.selectbox(
                        "Via de administracion",
                        ["Via Oral", "Via Endovenosa", "Via Intramuscular", "Via Subcutanea", "Via Topica", "Via Inhalatoria", "Otra"],
                    )
                    frecuencia = st.selectbox(
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
                    dias = st.number_input("Dias", min_value=1, max_value=90, value=7)
                else:
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
            else:
                via = "Via Endovenosa"
                frecuencia = "Infusion continua"
                if es_movil:
                    solucion = st.selectbox(
                        "Solucion principal",
                        [
                            "Dextrosa 5%",
                            "Fisiologico 0.9%",
                            "Ringer lactato",
                            "Mixta",
                            "Otra",
                        ],
                        key="solucion_receta",
                    )
                    volumen_ml = st.number_input("Volumen total (ml)", min_value=0, step=50, value=500, key="volumen_receta")
                    dias = st.number_input("Dias", min_value=1, max_value=90, value=1, key="dias_infusion_receta")
                    velocidad_ml_h = st.number_input(
                        "Velocidad (ml/h)",
                        min_value=0.0,
                        step=1.0,
                        value=21.0,
                        key="velocidad_receta",
                    )
                    hora_inicio = st.time_input(
                        "Hora inicial",
                        value=dt_time(8, 0),
                        key="hora_inicio_infusion_receta",
                    )
                else:
                    c1, c2, c3 = st.columns([2, 1, 1])
                    solucion = c1.selectbox(
                        "Solucion principal",
                        [
                            "Dextrosa 5%",
                            "Fisiologico 0.9%",
                            "Ringer lactato",
                            "Mixta",
                            "Otra",
                        ],
                        key="solucion_receta",
                    )
                    volumen_ml = c2.number_input("Volumen total (ml)", min_value=0, step=50, value=500, key="volumen_receta")
                    dias = c3.number_input("Dias", min_value=1, max_value=90, value=1, key="dias_infusion_receta")

                    c4, c5 = st.columns([1, 2])
                    velocidad_ml_h = c4.number_input(
                        "Velocidad (ml/h)",
                        min_value=0.0,
                        step=1.0,
                        value=21.0,
                        key="velocidad_receta",
                    )
                    hora_inicio = c5.time_input(
                        "Hora inicial",
                        value=dt_time(8, 0),
                        key="hora_inicio_infusion_receta",
                    )
                horarios_sugeridos = [hora_inicio.strftime("%H:%M")]
                detalle_infusion = st.text_area(
                    "Notas / evolucion del medico (opcional)",
                    placeholder="Si quiere agregar alguna indicacion adicional o detalle sobre el plan, escribalo aqui.",
                    key="detalle_infusion_receta",
                    height=80,
                )
                st.caption(f"Horario visible en la sabana diaria: {hora_inicio.strftime('%H:%M')} — {int(velocidad_ml_h) if velocidad_ml_h else '?'} ml/h")
                alternar_con = ""
                plan_hidratacion = []

            if es_movil:
                medico_nombre = st.text_input("Nombre del medico", value=user.get("nombre", ""))
                medico_matricula = st.text_input("Matricula profesional")
            else:
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

            med_final_preview = med_manual.strip().title() if med_manual.strip() else med_vademecum
            if (
                med_final_preview
                and med_final_preview != "-- Seleccionar del vademecum --"
                and tipo_indicacion == "Medicacion"
            ):
                _nombre_norm = med_final_preview.strip().lower()
                _activas_dup = [
                    r for r in st.session_state.get("indicaciones_db", [])
                    if r.get("paciente") == paciente_sel
                    and str(r.get("estado_receta", "Activa")).strip().lower() not in ("suspendida", "cancelada")
                    and _nombre_norm in str(r.get("med") or "").lower()
                ]
                if _activas_dup:
                    st.warning(
                        f"🟡 **Posible duplicado**: '{med_final_preview}' ya figura en la medicación activa "
                        f"({'1 indicación' if len(_activas_dup) == 1 else f'{len(_activas_dup)} indicaciones'}). "
                        "Verificá antes de prescribir."
                    )

            if st.button("Guardar prescripcion medica", width="stretch", type="primary"):
                med_final = med_manual.strip().title() if med_manual.strip() else med_vademecum
                if tipo_indicacion == "Medicacion" and (not med_final or med_final == "-- Seleccionar del vademecum --"):
                    st.error("Debe seleccionar o escribir un medicamento.")
                elif tipo_indicacion == "Infusion / hidratacion" and not solucion.strip():
                    st.error("Debe indicar la solucion principal.")
                else:
                    if not medico_matricula.strip():
                        st.error("Debe ingresar la matricula del medico.")
                    else:
                        firma_b64 = firma_a_base64(
                            canvas_image_data=firma_canvas.image_data if firma_canvas is not None else None,
                            uploaded_file=firma_subida,
                        )

                        texto_receta = _construir_texto_indicacion(
                            tipo_indicacion=tipo_indicacion,
                            med_final=med_final,
                            via=via,
                            frecuencia=frecuencia,
                            dias=dias,
                            solucion=solucion,
                            volumen_ml=volumen_ml,
                            velocidad_ml_h=velocidad_ml_h,
                            alternar_con=alternar_con,
                            detalle_infusion=detalle_infusion,
                            plan_hidratacion=plan_hidratacion,
                        )
                        # Safe initialization antes de append
                        if "indicaciones_db" not in st.session_state or not isinstance(st.session_state["indicaciones_db"], list):
                            st.session_state["indicaciones_db"] = []
                        st.session_state["indicaciones_db"].append(
                            {
                                "paciente": paciente_sel,
                                "med": texto_receta,
                                "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                                "dias_duracion": dias,
                                "medico_nombre": medico_nombre.strip(),
                                "medico_matricula": medico_matricula.strip(),
                                "firma_b64": firma_b64,
                                "firmado_por": nombre_usuario,
                                "estado_clinico": "Activa",
                                "estado_receta": "Activa",
                                "frecuencia": frecuencia,
                                "hora_inicio": hora_inicio.strftime("%H:%M"),
                                "horarios_programados": horarios_sugeridos,
                                "tipo_indicacion": tipo_indicacion,
                                "solucion": solucion,
                                "volumen_ml": volumen_ml,
                                "velocidad_ml_h": velocidad_ml_h,
                                "alternar_con": alternar_con,
                                "detalle_infusion": detalle_infusion,
                                "plan_hidratacion": plan_hidratacion,
                                "fecha_estado": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                                "profesional_estado": nombre_usuario,
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
                        
                        # Dual-write a PostgreSQL
                        from core.nextgen_sync import sync_receta_to_sql
                        datos_receta_completa = {
                            "dias_duracion": dias,
                            "medico_nombre": medico_nombre.strip(),
                            "medico_matricula": medico_matricula.strip(),
                            "firma_b64": firma_b64,
                            "hora_inicio": hora_inicio.strftime("%H:%M"),
                            "horarios_programados": horarios_sugeridos,
                            "solucion": solucion,
                            "volumen_ml": volumen_ml,
                            "velocidad_ml_h": velocidad_ml_h,
                            "alternar_con": alternar_con,
                            "detalle_infusion": detalle_infusion,
                            "plan_hidratacion": plan_hidratacion
                        }
                        sync_receta_to_sql(paciente_sel, med_final, via, frecuencia, tipo_indicacion, datos_receta_completa)
                        
                        st.session_state["_rx_sql_invalidar"] = True
                        guardar_datos(spinner=True)
                        queue_toast(f"Prescripcion de {med_final} guardada con firma medica.")
                        st.rerun()

    if puede_cargar_papel:
        st.markdown(
            """
            <div class="mc-rx-section-head mc-rx-section-head--tight">
                <h3 class="mc-rx-section-title">Indicación en papel o PDF</h3>
                <p class="mc-rx-section-sub">
                    Digitalizá la orden firmada para que forme parte del legajo electrónico con médico, matrícula y adjunto.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            st.caption(
                "El archivo y los datos quedan vinculados al paciente con registro de auditoría al guardar."
            )
            tipo_indicacion_papel = st.radio(
                "Tipo de indicacion a cargar",
                ["Medicacion", "Infusion / hidratacion"],
                horizontal=True,
                key="tipo_indicacion_papel_receta",
            )
            if es_movil:
                medico_papel = st.text_input(
                    "Medico que indica",
                    key="medico_papel_nombre",
                    value=user.get("nombre", "") if rol not in {"Operativo", "Enfermeria"} else "",
                )
                matricula_papel = st.text_input("Matricula del medico", key="medico_papel_matricula")
                dias_papel = st.number_input("Dias indicados", min_value=1, max_value=90, value=7, key="dias_papel_receta")
                hora_papel = st.time_input("Hora inicial", value=dt_time(8, 0), key="hora_papel_receta")
            else:
                c_p1, c_p2 = st.columns(2)
                medico_papel = c_p1.text_input(
                    "Medico que indica",
                    key="medico_papel_nombre",
                    value=user.get("nombre", "") if rol not in {"Operativo", "Enfermeria"} else "",
                )
                matricula_papel = c_p2.text_input("Matricula del medico", key="medico_papel_matricula")
                c_p3, c_p4 = st.columns([1, 2])
                dias_papel = c_p3.number_input("Dias indicados", min_value=1, max_value=90, value=7, key="dias_papel_receta")
                hora_papel = c_p4.time_input("Hora inicial", value=dt_time(8, 0), key="hora_papel_receta")

            horarios_papel = []
            detalle_papel = ""
            solucion_papel = ""
            volumen_papel = 0
            velocidad_papel = None
            alternar_papel = ""
            plan_papel = []

            if tipo_indicacion_papel == "Medicacion":
                detalle_papel = st.text_area(
                    "Resumen de la indicacion",
                    key="detalle_papel_receta",
                    placeholder="Ej: Ceftriaxona 1g EV cada 12 horas por 7 dias. Control de temperatura y signos vitales.",
                )
                horarios_papel_txt = st.text_input(
                    "Horarios programados (opcional)",
                    key="horarios_papel_receta",
                    placeholder="Ej: 08:00 | 16:00 | 22:00",
                )
                horarios_papel = parse_horarios_programados(horarios_papel_txt)
                if horarios_papel:
                    st.caption(f"Quedaran visibles en la sabana diaria: {' | '.join(horarios_papel)}")
            else:
                if es_movil:
                    solucion_papel = st.selectbox(
                        "Solucion principal",
                        ["Dextrosa 5%", "Fisiologico 0.9%", "Ringer lactato", "Mixta", "Otra"],
                        key="solucion_papel_receta",
                    )
                    volumen_papel = st.number_input(
                        "Volumen total (ml)",
                        min_value=0,
                        step=50,
                        value=500,
                        key="volumen_papel_receta",
                    )
                else:
                    c_inf_p1, c_inf_p2 = st.columns([2, 1])
                    solucion_papel = c_inf_p1.selectbox(
                        "Solucion principal",
                        ["Dextrosa 5%", "Fisiologico 0.9%", "Ringer lactato", "Mixta", "Otra"],
                        key="solucion_papel_receta",
                    )
                    volumen_papel = c_inf_p2.number_input(
                        "Volumen total (ml)",
                        min_value=0,
                        step=50,
                        value=500,
                        key="volumen_papel_receta",
                    )
                velocidad_papel = st.number_input(
                    "Velocidad (ml/h)",
                    min_value=0.0,
                    step=1.0,
                    value=21.0,
                    key="velocidad_papel_receta",
                )
                detalle_papel = st.text_area(
                    "Notas / evolucion del medico (opcional)",
                    key="detalle_papel_infusion_receta",
                    placeholder="Si quiere agregar alguna indicacion adicional o detalle sobre el plan, escribalo aqui.",
                    height=80,
                )
                horarios_papel = [hora_papel.strftime("%H:%M")]
                alternar_papel = ""
                plan_papel = []
                st.caption(f"Horario visible en la sabana diaria: {hora_papel.strftime('%H:%M')} — {int(velocidad_papel) if velocidad_papel else '?'} ml/h")
            # --- Boton de guardado digital rapido (solo infusion, sin adjunto requerido) ---
            if tipo_indicacion_papel == "Infusion / hidratacion":
                if st.button("Guardar infusion (prescripcion digital)", width="stretch", type="primary", key="guardar_infusion_digital"):
                    if not medico_papel.strip() or not matricula_papel.strip():
                        st.error("Debe completar medico y matricula.")
                    else:
                        texto_inf = _construir_texto_indicacion(
                            tipo_indicacion="Infusion / hidratacion",
                            via="Via Endovenosa",
                            frecuencia="Infusion continua",
                            dias=dias_papel,
                            solucion=solucion_papel,
                            volumen_ml=volumen_papel,
                            velocidad_ml_h=velocidad_papel,
                            detalle_infusion=detalle_papel.strip(),
                        )
                        reg_inf = {
                            "paciente": paciente_sel,
                            "med": texto_inf,
                            "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                            "dias_duracion": dias_papel,
                            "medico_nombre": medico_papel.strip(),
                            "medico_matricula": matricula_papel.strip(),
                            "firma_b64": "",
                            "firmado_por": nombre_usuario,
                            "estado_clinico": "Activa",
                            "estado_receta": "Activa",
                            "frecuencia": "Infusion continua",
                            "hora_inicio": horarios_papel[0] if horarios_papel else hora_papel.strftime("%H:%M"),
                            "horarios_programados": horarios_papel,
                            "tipo_indicacion": "Infusion / hidratacion",
                            "solucion": solucion_papel,
                            "volumen_ml": volumen_papel,
                            "velocidad_ml_h": velocidad_papel,
                            "detalle_infusion": detalle_papel.strip(),
                            "plan_hidratacion": [],
                            "fecha_estado": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                            "profesional_estado": nombre_usuario,
                            "matricula_estado": user.get("matricula", ""),
                            "origen_registro": "Prescripcion digital de infusion",
                            "empresa": mi_empresa,
                        }
                        # Safe initialization antes de append
                        if "indicaciones_db" not in st.session_state or not isinstance(st.session_state["indicaciones_db"], list):
                            st.session_state["indicaciones_db"] = []
                        st.session_state["indicaciones_db"].append(reg_inf)
                        registrar_auditoria_legal(
                            "Medicacion",
                            paciente_sel,
                            "Infusion prescripta digitalmente",
                            medico_papel.strip(),
                            matricula_papel.strip(),
                            texto_inf,
                        )
                        from core.nextgen_sync import sync_receta_to_sql
                        sync_receta_to_sql(
                            paciente_sel, f"{solucion_papel} {int(volumen_papel)} ml",
                            "Via Endovenosa", "Infusion continua", "Infusion / hidratacion",
                            {"velocidad_ml_h": velocidad_papel, "dias_duracion": dias_papel,
                             "hora_inicio": horarios_papel[0] if horarios_papel else "",
                             "medico_nombre": medico_papel.strip(), "medico_matricula": matricula_papel.strip(),
                             "detalle_infusion": detalle_papel.strip()}
                        )
                        st.session_state["_rx_sql_invalidar"] = True
                        guardar_datos(spinner=True)
                        queue_toast(f"Infusion {solucion_papel} {int(volumen_papel)} ml a {int(velocidad_papel or 0)} ml/h guardada.")
                        st.rerun()
                st.caption("Si tenes la orden en papel, adjuntala abajo para dejar el respaldo legal completo.")

            adjunto_papel = st.file_uploader(
                "Subir orden medica en papel o PDF (opcional para infusion)",
                type=["pdf", "png", "jpg", "jpeg"],
                key="adjunto_papel_receta",
            )
            if st.button("Guardar indicacion en papel", width="stretch", key="guardar_indicacion_papel"):
                if not medico_papel.strip() or not matricula_papel.strip():
                    st.error("Debe completar medico y matricula para dejar respaldo legal.")
                elif tipo_indicacion_papel == "Medicacion" and not detalle_papel.strip():
                    st.error("Debe resumir la indicacion medica para que se vea rapido en la guardia.")
                elif adjunto_papel is None:
                    st.error("Debe adjuntar la orden medica escaneada o fotografiada.")
                else:
                    adjunto_b64, adjunto_nombre, adjunto_tipo = _archivo_a_base64(adjunto_papel)
                    texto_guardado = _construir_texto_indicacion(
                        tipo_indicacion=tipo_indicacion_papel,
                        med_final=detalle_papel.strip(),
                        via="Via Endovenosa" if tipo_indicacion_papel == "Infusion / hidratacion" else "",
                        frecuencia="Infusion continua" if tipo_indicacion_papel == "Infusion / hidratacion" else "",
                        dias=dias_papel,
                        solucion=solucion_papel,
                        volumen_ml=volumen_papel,
                        velocidad_ml_h=velocidad_papel,
                        alternar_con=alternar_papel,
                        detalle_infusion=detalle_papel.strip() if tipo_indicacion_papel == "Infusion / hidratacion" else "",
                        plan_hidratacion=plan_papel,
                    )
                    registro = {
                        "paciente": paciente_sel,
                        "med": texto_guardado,
                        "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                        "dias_duracion": dias_papel,
                        "medico_nombre": medico_papel.strip(),
                        "medico_matricula": matricula_papel.strip(),
                        "firma_b64": "",
                        "firmado_por": nombre_usuario,
                        "estado_clinico": "Activa",
                        "estado_receta": "Activa",
                        "frecuencia": "Infusion continua" if tipo_indicacion_papel == "Infusion / hidratacion" else "",
                        "hora_inicio": horarios_papel[0] if horarios_papel else hora_papel.strftime("%H:%M"),
                        "horarios_programados": horarios_papel,
                        "tipo_indicacion": tipo_indicacion_papel,
                        "solucion": solucion_papel,
                        "volumen_ml": volumen_papel,
                        "velocidad_ml_h": velocidad_papel,
                        "alternar_con": alternar_papel,
                        "detalle_infusion": detalle_papel.strip() if tipo_indicacion_papel == "Infusion / hidratacion" else "",
                        "plan_hidratacion": plan_papel,
                        "fecha_estado": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                        "profesional_estado": nombre_usuario,
                        "matricula_estado": user.get("matricula", ""),
                        "origen_registro": "Indicacion medica en papel",
                        "adjunto_papel_b64": adjunto_b64,
                        "adjunto_papel_nombre": adjunto_nombre,
                        "adjunto_papel_tipo": adjunto_tipo,
                        "empresa": mi_empresa,
                    }
                    # Safe initialization antes de append
                    if "indicaciones_db" not in st.session_state or not isinstance(st.session_state["indicaciones_db"], list):
                        st.session_state["indicaciones_db"] = []
                    st.session_state["indicaciones_db"].append(registro)
                    registrar_auditoria_legal(
                        "Medicacion",
                        paciente_sel,
                        "Indicacion medica en papel cargada",
                        user.get("nombre", ""),
                        user.get("matricula", ""),
                        f"Medico: {medico_papel.strip()} | Matricula: {matricula_papel.strip()} | {detalle_papel.strip()}",
                    )
                    from core.nextgen_sync import sync_receta_to_sql as _sync_rx
                    _med_papel = detalle_papel.strip() if tipo_indicacion_papel == "Medicacion" else f"{solucion_papel} {int(volumen_papel)} ml"
                    _sync_rx(
                        paciente_sel, _med_papel,
                        "Via Endovenosa" if tipo_indicacion_papel == "Infusion / hidratacion" else "",
                        "Infusion continua" if tipo_indicacion_papel == "Infusion / hidratacion" else "",
                        tipo_indicacion_papel,
                        {"velocidad_ml_h": velocidad_papel, "dias_duracion": dias_papel,
                         "hora_inicio": horarios_papel[0] if horarios_papel else "",
                         "medico_nombre": medico_papel.strip(), "medico_matricula": matricula_papel.strip(),
                         "origen": "papel", "detalle_infusion": detalle_papel.strip()}
                    )
                    st.session_state["_rx_sql_invalidar"] = True
                    guardar_datos(spinner=True)
                    queue_toast("La indicacion medica en papel quedo guardada y disponible en el historial.")
                    st.rerun()

    st.divider()
    
    # --- SWITCH FINAL: LECTURA DESDE POSTGRESQL ---
    import time as _time
    from core.nextgen_sync import _obtener_uuid_paciente, _obtener_uuid_empresa
    
    recs_todas = []
    admin_hoy = []
    fecha_hoy = ahora().strftime("%d/%m/%Y")
    uso_sql_recetas = False
    _RECETAS_SQL_TTL = 30  # segundos antes de refrescar desde Supabase
    
    try:
        partes = paciente_sel.split(" - ")
        if len(partes) > 1:
            dni = partes[1].strip()
            empresa = st.session_state.get("u_actual", {}).get("empresa", "Clinica General")
            empresa_id = _obtener_uuid_empresa(empresa)
            
            if empresa_id:
                pac_uuid = _obtener_uuid_paciente(dni, empresa_id)
                if pac_uuid:
                    # Cache de 30s en session_state: evita 2 queries Supabase por rerun
                    _ck = f"_rx_sql_{pac_uuid}"
                    if st.session_state.pop("_rx_sql_invalidar", False):
                        st.session_state.pop(_ck, None)
                    _cached = st.session_state.get(_ck, {})
                    _cache_age = _time.monotonic() - _cached.get("ts", 0)
                    if _cache_age < _RECETAS_SQL_TTL and _cached.get("fecha") == fecha_hoy:
                        inds_sql = _cached["inds"]
                        adms_sql = _cached["adms"]
                    else:
                        from core.database import supabase
                        fecha_hoy_iso = ahora().strftime("%Y-%m-%d")
                        res_ind = supabase.table("indicaciones").select("*").eq("paciente_id", pac_uuid).order("fecha_indicacion", desc=True).execute()
                        inds_sql = res_ind.data if res_ind and res_ind.data else []
                        res_adm = supabase.table("administracion_med").select("*").eq("paciente_id", pac_uuid).gte("fecha_registro", f"{fecha_hoy_iso}T00:00:00").lte("fecha_registro", f"{fecha_hoy_iso}T23:59:59").execute()
                        adms_sql = res_adm.data if res_adm and res_adm.data else []
                        st.session_state[_ck] = {"ts": _time.monotonic(), "fecha": fecha_hoy, "inds": inds_sql, "adms": adms_sql}
                    uso_sql_recetas = True
                    
                    # Mapear indicaciones SQL a formato JSON legacy
                    for ind in inds_sql:
                        extra = ind.get("datos_extra", {}) or {}
                        recs_todas.append({
                            "paciente": paciente_sel,
                            "med": ind.get("medicamento", ""),
                            "fecha": ind.get("fecha_indicacion", "")[:16].replace("T", " ") if ind.get("fecha_indicacion") else "",
                            "estado_receta": ind.get("estado", "Activa"),
                            "estado_clinico": ind.get("estado", "Activa"),
                            "via": ind.get("via_administracion", ""),
                            "frecuencia": ind.get("frecuencia", ""),
                            "tipo_indicacion": ind.get("tipo_indicacion", ""),
                            "dias_duracion": extra.get("dias_duracion", 7),
                            "medico_nombre": extra.get("medico_nombre", ""),
                            "medico_matricula": extra.get("medico_matricula", ""),
                            "firma_b64": extra.get("firma_b64", ""),
                            "hora_inicio": extra.get("hora_inicio", ""),
                            "horarios_programados": extra.get("horarios_programados", []),
                            "solucion": extra.get("solucion", ""),
                            "volumen_ml": extra.get("volumen_ml", 0),
                            "velocidad_ml_h": extra.get("velocidad_ml_h", None),
                            "alternar_con": extra.get("alternar_con", ""),
                            "detalle_infusion": extra.get("detalle_infusion", ""),
                            "plan_hidratacion": extra.get("plan_hidratacion", [])
                        })
                        
                    # Mapear administraciones SQL a formato JSON legacy
                    for adm in adms_sql:
                        extra = adm.get("datos_extra", {}) or {}
                        med_name = extra.get("medicamento", "")
                                
                        admin_hoy.append({
                            "paciente": paciente_sel,
                            "fecha": fecha_hoy,
                            "med": med_name,
                            "horario_programado": adm.get("horario_programado", ""),
                            "hora": extra.get("hora_real_administracion", adm.get("hora_real_administracion", "")),
                            "estado": adm.get("estado", ""),
                            "motivo": adm.get("motivo_no_realizada", ""),
                            "firma": extra.get("firma", ""),
                            "matricula_profesional": extra.get("matricula_profesional", ""),
                            "usuario_login": extra.get("usuario_login", "")
                        })
    except Exception as e:
        from core.app_logging import log_event
        log_event("recetas_sql", f"error_lectura:{type(e).__name__}")

    if not uso_sql_recetas:
        recs_todas = [r for r in st.session_state.get("indicaciones_db", []) if r.get("paciente") == paciente_sel]
        admin_hoy = [
            a
            for a in st.session_state.get("administracion_med_db", [])
            if a.get("paciente") == paciente_sel and a.get("fecha") == fecha_hoy
        ]
    # ----------------------------------------------

    recs_activas = [r for r in recs_todas if r.get("estado_receta", "Activa") == "Activa"]

    if recs_activas:
        st.subheader("Administración del turno")
        limite_guardia = seleccionar_limite_registros(
            "Indicaciones activas visibles",
            len(recs_activas),
            key=f"recetas_guardia_limite_{paciente_sel}",
            default=12,
            opciones=(6, 12, 20, 30, 40),
        )
        recs_guardia = recs_activas[:limite_guardia]
        if len(recs_activas) > len(recs_guardia):
            st.caption(f"Se muestran {len(recs_guardia)} de {len(recs_activas)} indicaciones activas para mantener la vista agil en equipos lentos.")
        plan_dia = []
        sabana_resumen = []
        for r in recs_guardia:
            med_texto = str(r.get("med", "") or "")
            partes = med_texto.split(" | ")
            nombre = _extraer_nombre_medicacion(med_texto)
            via_texto = partes[1].replace("Via: ", "") if len(partes) > 1 and "Via:" in partes[1] else r.get("via", "")
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
                    estado_actual = admin_reg.get("estado", "Pendiente") if admin_reg else "Pendiente"
                    plan_dia.append(
                        {
                            "OK": _estado_icono(estado_actual),
                            "Hora programada": horario,
                            "Hora realizada": admin_reg.get("hora", "") if admin_reg else "",
                            "Medicamento": nombre,
                            "Detalle / velocidad": _detalle_horario_infusion(r, horario),
                            "Via": via_texto or "S/D",
                            "Frecuencia": frecuencia_texto or "S/D",
                            "Estado": _estado_legible(estado_actual),
                            "Observacion": admin_reg.get("motivo", "") if admin_reg else "",
                            "Registrado por": _firma_trazabilidad_admin(admin_reg) if admin_reg else "",
                        }
                    )
            else:
                admin_reg = next((a for a in admin_hoy if a.get("med") == nombre), None)
                estado_actual = admin_reg.get("estado", "Pendiente") if admin_reg else "Pendiente"
                plan_dia.append(
                    {
                        "OK": _estado_icono(estado_actual),
                        "Hora programada": "A demanda",
                        "Hora realizada": admin_reg.get("hora", "") if admin_reg else "",
                        "Medicamento": nombre,
                        "Detalle / velocidad": _detalle_horario_infusion(r, ""),
                        "Via": via_texto or "S/D",
                        "Frecuencia": frecuencia_texto or "A demanda",
                        "Estado": _estado_legible(estado_actual),
                        "Observacion": admin_reg.get("motivo", "") if admin_reg else "",
                        "Registrado por": _firma_trazabilidad_admin(admin_reg) if admin_reg else "",
                    }
                )

        plan_dia_df = pd.DataFrame(plan_dia)
        if not plan_dia_df.empty:
            plan_dia_df["_orden"] = plan_dia_df["Hora programada"].apply(_orden_horario_programado)
            plan_dia_df = plan_dia_df.sort_values(by=["_orden", "Medicamento"]).drop(columns=["_orden"])
        tabla_guardia_df = _tabla_guardia_operativa(plan_dia_df)
        tabla_guardia_detallada_df = _tabla_guardia_detallada(plan_dia_df)
        sabana_resumen_df = pd.DataFrame(sabana_resumen)

        matriz_registro_rows, horas_mar, matriz_registro_map = _construir_matriz_registro_24h(plan_dia_df)
        columnas_tabla = [
            "Hora programada",
            "Medicamento",
            "Detalle / velocidad",
            "Via",
            "Frecuencia",
            "Estado",
            "Hora realizada",
            "Registrado por",
            "Observacion",
        ]
        plan_hidratacion_rows = []
        for _rx in recs_guardia:
            _plan = _rx.get("plan_hidratacion") or []
            if not _plan:
                continue
            _mn = _extraer_nombre_medicacion(str(_rx.get("med", "")))
            for _it in _plan:
                if isinstance(_it, dict):
                    _fila = dict(_it)
                    _fila["Medicacion"] = _mn
                    plan_hidratacion_rows.append(_fila)

        st.markdown(
            '<p style="margin:0 0 0.35rem 0;font-size:0.78rem;font-weight:800;letter-spacing:0.12em;text-transform:uppercase;color:rgba(148,163,184,0.95);">Resumen del día</p>',
            unsafe_allow_html=True,
        )
        realizadas_count = int((plan_dia_df.get("Estado") == "Realizada").sum()) if not plan_dia_df.empty else 0
        no_realizadas_count = (
            int(plan_dia_df["Estado"].astype(str).str.contains("No realizada", case=False, na=False).sum())
            if not plan_dia_df.empty
            else 0
        )
        pendientes_count = int((plan_dia_df.get("Estado") == "Pendiente").sum()) if not plan_dia_df.empty else 0
        if es_movil:
            c_res1, c_res2 = st.columns(2)
            c_res1.metric("Realizadas", realizadas_count)
            c_res2.metric("No realizadas", no_realizadas_count)
            st.metric("Pendientes", pendientes_count)
        else:
            c_res1, c_res2, c_res3 = st.columns(3)
            c_res1.metric("Realizadas", realizadas_count)
            c_res2.metric("No realizadas", no_realizadas_count)
            c_res3.metric("Pendientes", pendientes_count)

        vista_guardia = st.radio(
            "Vista de administración",
            ["Tarjetas (alternativa)", "Cortina empresarial"] if es_movil else ["Cortina empresarial", "Tarjetas (alternativa)"],
            horizontal=True,
            index=0,
            key=f"recetas_vista_guardia_{paciente_sel}",
        )

        if vista_guardia == "Tarjetas (alternativa)":
            _render_sabana_compacta(plan_dia_df, paciente_sel, mi_empresa, user, fecha_hoy, puede_registrar_dosis)

        if puede_registrar_dosis and matriz_registro_rows:
            columnas_mar = ["Medicacion", "Via", "Frecuencia"] + horas_mar + ["A demanda"]
            matriz_registro_df = pd.DataFrame(matriz_registro_rows)
            matriz_registro_df = matriz_registro_df[columnas_mar]
            estado_celda_opciones = ["⬜", "🟨 Pendiente", "🟩 Realizada", "🟥 No realizada"]
            for hora_col in horas_mar + ["A demanda"]:
                matriz_registro_df[hora_col] = (
                    matriz_registro_df[hora_col]
                    .astype(str)
                    .replace(
                        {
                            "": "⬜",
                            "Pendiente": "🟨 Pendiente",
                            "Realizada": "🟩 Realizada",
                            "No realizada": "🟥 No realizada",
                        }
                    )
                )

            column_config = {
                "Medicacion": st.column_config.TextColumn("Medicacion", width="large"),
                "Via": st.column_config.TextColumn("Via", width="small"),
                "Frecuencia": st.column_config.TextColumn("Frecuencia", width="small"),
            }
            # Referencia visual para carga rápida de enfermería.
            st.markdown("⬜ **Sin horario/celda vacía** · 🟩 **Realizada** · 🟥 **No realizada** (requiere motivo) · 🟨 **Pendiente**")
            for hora_col in horas_mar + ["A demanda"]:
                column_config[hora_col] = st.column_config.SelectboxColumn(
                    hora_col,
                    options=estado_celda_opciones,
                    required=False,
                    width="small",
                )

            editor_mar_df = st.data_editor(
                matriz_registro_df,
                hide_index=True,
                width="stretch",
                disabled=["Medicacion", "Via", "Frecuencia"],
                column_config=column_config,
                key=f"matriz_mar_editor_{paciente_sel}_{fecha_hoy}",
            )
            motivo_no_realizada = st.text_input(
                "Motivo clínico para celdas en rojo (No realizada)",
                placeholder="Ej. Paciente ausente, rechazo, ayuno, orden médica...",
                key=f"motivo_no_realizada_mar_{paciente_sel}_{fecha_hoy}",
            )

            if st.button(
                "Guardar estados de cortina",
                width="stretch",
                key=f"guardar_mar_{paciente_sel}_{fecha_hoy}",
            ):
                registros_guardados = 0
                requiere_motivo = False
                for row_idx in range(len(editor_mar_df)):
                    for hora_col in horas_mar + ["A demanda"]:
                        original_valor = str(matriz_registro_df.at[row_idx, hora_col] or "").strip()
                        nuevo_valor = str(editor_mar_df.at[row_idx, hora_col] or "").strip()
                        if not original_valor and not nuevo_valor:
                            continue
                        if nuevo_valor in {"", "⬜"} or nuevo_valor == original_valor:
                            continue

                        metas = matriz_registro_map.get((row_idx, hora_col), [])
                        if not metas:
                            continue

                        for meta in metas:
                            nombre_med = str(meta.get("medicamento", "") or "").strip()
                            horario_sel = str(meta.get("horario_programado", "") or "").strip()
                            if not nombre_med:
                                continue

                            if nuevo_valor == "🟩 Realizada":
                                _guardar_administracion_medicacion(
                                    paciente_sel,
                                    mi_empresa,
                                    user,
                                    nombre_med,
                                    fecha_hoy,
                                    horario_sel,
                                    "Realizada",
                                )
                            elif nuevo_valor == "🟥 No realizada":
                                if not str(motivo_no_realizada or "").strip():
                                    requiere_motivo = True
                                    continue
                                _registrar_administracion_dosis(
                                    paciente_sel,
                                    mi_empresa,
                                    user,
                                    fecha_hoy,
                                    nombre_med,
                                    horario_sel,
                                    "No realizada / Suspendida",
                                    str(motivo_no_realizada or "").strip(),
                                    hora_real_admin=None,
                                )
                            elif nuevo_valor == "🟨 Pendiente":
                                continue
                            registros_guardados += 1

                if requiere_motivo:
                    st.error("Para guardar celdas en rojo, completá el motivo clínico.")
                    return
                if registros_guardados:
                    st.session_state["_rx_sql_invalidar"] = True
                    guardar_datos(spinner=True)
                    queue_toast(f"Se guardaron {registros_guardados} cambios de estado en la cortina.")
                    st.rerun()
                else:
                    st.info("No hay cambios de estado para guardar.")

        if not plan_dia_df.empty:
            with st.expander("Ver tabla de referencia (opcional)", expanded=False):
                df_plan_visible = pd.DataFrame(
                    {
                        "Hora": plan_dia_df["Hora programada"],
                        "Medicacion": plan_dia_df["Medicamento"],
                        "Indicacion": plan_dia_df.apply(
                            lambda fila: " | ".join(
                                [
                                    str(fila.get("Solucion", "") or "").strip(),
                                    str(fila.get("ML/h", "") or "").strip(),
                                    str(fila.get("Detalle / velocidad", "") or "").strip(),
                                ]
                            ).strip(" |"),
                            axis=1,
                        ),
                        "Via / Frecuencia": plan_dia_df.apply(
                            lambda fila: " | ".join(
                                [
                                    str(fila.get("Via", "") or "").strip(),
                                    str(fila.get("Frecuencia", "") or "").strip(),
                                ]
                            ).strip(" |"),
                            axis=1,
                        ),
                        "Estado": plan_dia_df["Estado"],
                        "Hora real": plan_dia_df["Hora realizada"],
                        "Observacion": plan_dia_df["Observacion"],
                        "Registrado por": plan_dia_df["Registrado por"],
                    }
                )
                mostrar_tabla_planilla = st.checkbox(
                    "Usar tabla ancha",
                    value=False,
                    key=f"mostrar_tabla_plan_{paciente_sel}_{fecha_hoy}",
                )
                if mostrar_tabla_planilla:
                    _render_tabla_clinica(
                        df_plan_visible,
                        key=f"plan_{paciente_sel}",
                        max_height=300 if es_movil else (420 if not anticolapso_activo() else 320),
                        sticky_first_col=False,
                    )
                else:
                    if es_movil and len(df_plan_visible) <= 4:
                        _h_tarjetas_plan = None
                    else:
                        _h_tarjetas_plan = 280 if es_movil else (320 if anticolapso_activo() else 480)
                    with st.container(height=_h_tarjetas_plan):
                        _render_dataframe_filas_tarjetas(df_plan_visible)

        if plan_hidratacion_rows:
            st.markdown(
                '<h4 class="mc-rx-table-zone-title">Plan de hidratación parenteral</h4>',
                unsafe_allow_html=True,
            )
            _render_tabla_clinica(
                pd.DataFrame(plan_hidratacion_rows),
                key=f"hidra_{paciente_sel}",
                max_height=240 if es_movil else 320,
                sticky_first_col=False,
            )

        if sabana_resumen:
            with st.expander("Ver resumen por indicación (opcional)", expanded=False):
                _render_tabla_clinica(
                    pd.DataFrame(sabana_resumen),
                    key=f"resumen_{paciente_sel}",
                    max_height=220 if es_movil else 260,
                    sticky_first_col=False,
                )

        if puede_registrar_dosis:
            if es_movil or vista_guardia == "Tarjetas (alternativa)":
                registro_container = st.expander(
                    "Registro manual / no realizada / otro horario", expanded=False
                )
            else:
                registro_container = st.container()
            with registro_container:
                st.markdown("#### Registro manual")
                with st.form("form_registro_dosis", clear_on_submit=True):
                    opciones_recetas = list(range(len(recs_activas)))
                    if es_movil:
                        receta_idx = st.selectbox(
                            "Medicacion a registrar",
                            opciones_recetas,
                            format_func=lambda idx: _etiqueta_receta(recs_activas[idx]),
                        )
                    else:
                        c_med, c_hora = st.columns([2, 1])
                        receta_idx = c_med.selectbox(
                            "Medicacion a registrar",
                            opciones_recetas,
                            format_func=lambda idx: _etiqueta_receta(recs_activas[idx]),
                        )
                    receta_actual = recs_activas[receta_idx]
                    if es_movil:
                        st.caption(f"Horarios: {format_horarios_receta(receta_actual)}")
                    else:
                        c_med.caption(f"Horarios: {format_horarios_receta(receta_actual)}")
                    horarios_receta = obtener_horarios_receta(receta_actual)
                    opciones_hora = horarios_receta or [f"{i:02d}:00" for i in range(24)]
                    hora_actual_str = f"{ahora().hour:02d}:00"
                    idx_hora = opciones_hora.index(hora_actual_str) if hora_actual_str in opciones_hora else 0
                    if es_movil:
                        hora_sel = st.selectbox(
                            "Horario programado",
                            opciones_hora if opciones_hora else ["A demanda"],
                            index=idx_hora if opciones_hora else 0,
                        )
                    else:
                        hora_sel = c_hora.selectbox(
                            "Horario programado",
                            opciones_hora if opciones_hora else ["A demanda"],
                            index=idx_hora if opciones_hora else 0,
                        )
                    estado_sel = st.radio("Estado", ["Realizada", "No realizada / Suspendida"], horizontal=True)
                    hora_real_manual = st.text_input(
                        "Hora real de administración o constancia (HH:MM, opcional)",
                        placeholder="Vacío = hora actual del servidor",
                        help="Si la dosis se dio u omitió en otro momento, registrá la hora real aquí.",
                    )
                    justificacion = st.text_input(
                        "Justificación clínica (obligatoria si no realizada: motivo, procedimiento, intolerancia, etc.)"
                    )
                    if st.form_submit_button("Guardar registro", width="stretch"):
                        nombre_med = _extraer_nombre_medicacion(receta_actual.get("med", ""))
                        if _registrar_administracion_dosis(
                            paciente_sel,
                            mi_empresa,
                            user,
                            fecha_hoy,
                            nombre_med,
                            hora_sel,
                            estado_sel,
                            justificacion,
                            hora_real_admin=hora_real_manual.strip() or None,
                        ):
                            queue_toast(f"Registro guardado para el horario {hora_sel}.")
                            st.rerun()
        else:
            st.caption("El registro de administracion queda deshabilitado para este rol.")

        st.divider()
        if puede_cambiar_estado:
            st.markdown(
                """
                <div class="mc-rx-section-head mc-rx-section-head--tight">
                    <h3 class="mc-rx-section-title">Gestión de indicaciones</h3>
                    <p class="mc-rx-section-sub">Suspender o modificar con motivo explícito; cada cambio queda auditado a nombre del profesional en sesión.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            opciones_recetas = list(range(len(recs_activas)))
            if es_movil:
                receta_idx = st.selectbox(
                    "Seleccionar indicacion",
                    opciones_recetas,
                    format_func=lambda idx: _etiqueta_receta(recs_activas[idx]),
                    key=f"recetas_editar_sel_{paciente_sel}",
                )
            else:
                c_ed1, c_ed2 = st.columns([3, 2])
                receta_idx = c_ed1.selectbox(
                    "Seleccionar indicacion",
                    opciones_recetas,
                    format_func=lambda idx: _etiqueta_receta(recs_activas[idx]),
                    key=f"recetas_editar_sel_{paciente_sel}",
                )
            receta_objetivo = recs_activas[receta_idx]
            if es_movil:
                accion_receta = st.selectbox("Accion", ["Suspender / Anular", "Editar indicacion"])
            else:
                accion_receta = c_ed2.selectbox("Accion", ["Suspender / Anular", "Editar indicacion"])
            nuevo_texto_receta = ""
            motivo_cambio = st.text_input("Motivo medico / legal del cambio", key="motivo_cambio_receta")
            if accion_receta == "Editar indicacion":
                nuevo_texto_receta = st.text_input(
                    "Modificar detalle",
                    value=receta_objetivo.get("med", ""),
                )
            if st.button("Aplicar cambios", width="stretch"):
                cambio_aplicado = False
                if accion_receta == "Editar indicacion" and not nuevo_texto_receta.strip():
                    st.error("Debes escribir el nuevo detalle de la indicacion.")
                else:
                    r = receta_objetivo
                    if accion_receta == "Suspender / Anular":
                        r["estado_receta"] = "Suspendida"
                        r["estado_clinico"] = "Suspendida"
                        r["fecha_suspension"] = ahora().strftime("%d/%m/%Y %H:%M:%S")
                        r["fecha_estado"] = r["fecha_suspension"]
                        r["profesional_estado"] = nombre_usuario
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
                        cambio_aplicado = True
                    elif accion_receta == "Editar indicacion":
                        r["estado_receta"] = "Modificada"
                        r["estado_clinico"] = "Modificada"
                        r["fecha_suspension"] = ahora().strftime("%d/%m/%Y %H:%M:%S")
                        r["fecha_estado"] = r["fecha_suspension"]
                        r["profesional_estado"] = nombre_usuario
                        r["matricula_estado"] = user.get("matricula", "")
                        r["motivo_estado"] = motivo_cambio.strip()
                        st.session_state["indicaciones_db"].append(
                            {
                                "paciente": paciente_sel,
                                "med": nuevo_texto_receta.strip(),
                                "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                                "dias_duracion": r.get("dias_duracion", 7),
                                "medico_nombre": r.get("medico_nombre", ""),
                                "medico_matricula": r.get("medico_matricula", ""),
                                "firma_b64": r.get("firma_b64", ""),
                                "firmado_por": nombre_usuario,
                                "estado_clinico": "Activa",
                                "estado_receta": "Activa",
                                "frecuencia": r.get("frecuencia", ""),
                                "hora_inicio": r.get("hora_inicio", ""),
                                "horarios_programados": r.get("horarios_programados", []),
                                "fecha_estado": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                                "profesional_estado": nombre_usuario,
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
                            f"Anterior: {r.get('med', '')} | Nueva: {nuevo_texto_receta.strip()} | Motivo: {motivo_cambio.strip()}",
                        )
                        cambio_aplicado = True
                if cambio_aplicado:
                    st.session_state["_rx_sql_invalidar"] = True
                    guardar_datos(spinner=True)
                    st.rerun()
        else:
            st.caption(
                "La suspension o modificacion de indicaciones queda reservada a medico, coordinacion o administracion con acceso total."
            )
    else:
        st.markdown(
            """
            <div class="mc-rx-callout-care" style="border-color:rgba(148,163,184,0.2);background:linear-gradient(90deg,rgba(30,41,59,0.5),rgba(15,23,42,0.4));">
                <span class="mc-rx-callout-ico" aria-hidden="true">📋</span>
                <p>
                    <strong>Sin indicaciones activas</strong> para este paciente. Cuando el médico prescriba o cargues una orden en papel,
                    aparecerá aquí la administración del turno con el mismo estándar de trazabilidad.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()
    if recs_todas:
        st.markdown(
            """
            <div class="mc-rx-section-head mc-rx-section-head--tight">
                <h3 class="mc-rx-section-title">Historial de prescripciones</h3>
                <p class="mc-rx-section-sub">Consulta de evolución terapéutica; activá la carga explícita para no afectar rendimiento.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        mostrar_historial = st.checkbox(
            "Cargar historial completo de prescripciones",
            value=False,
            key=f"mostrar_historial_recetas_{paciente_sel}",
        )
        if mostrar_historial:
            limite_hist = seleccionar_limite_registros(
                "Prescripciones a mostrar",
                len(recs_todas),
                key=f"limite_recetas_hist_{paciente_sel}",
                default=15,
                opciones=(10, 15, 20, 30, 50, 80),
            )

            altura_historial = None if es_movil and limite_hist <= 4 else (320 if es_movil else 450)
            with st.container(height=altura_historial):
                for idx, r in enumerate(reversed(recs_todas[-limite_hist:])):
                    with st.container(border=True):
                        estado_actual = r.get("estado_receta", "Activa")
                        if es_movil:
                            info_container = st.container()
                            action_container = st.container()
                        else:
                            info_container, action_container = st.columns([3, 1])
                        info_container.markdown(f"**{r.get('fecha', '-')}**")
                        info_container.markdown(
                            f"**Indicado por:** {r.get('medico_nombre', '-')} | **Matricula:** {r.get('medico_matricula', '-')}"
                        )
                        if r.get("origen_registro"):
                            info_container.caption(f"Origen: {r.get('origen_registro')}")
                        info_container.markdown(f"*{r.get('med', '')}*")
                        info_container.caption(f"Horarios: {format_horarios_receta(r)}")
                        if r.get("tipo_indicacion") == "Infusion / hidratacion":
                            detalle_inf = []
                            if r.get("velocidad_ml_h") not in ("", None):
                                detalle_inf.append(f"Velocidad: {r.get('velocidad_ml_h')} ml/h")
                            if r.get("alternar_con"):
                                detalle_inf.append(f"Alternar con: {r.get('alternar_con')}")
                            if detalle_inf:
                                info_container.caption(" | ".join(detalle_inf))
                            if r.get("plan_hidratacion"):
                                info_container.caption(f"Plan de hidratacion: {_resumen_plan_hidratacion(r.get('plan_hidratacion', []))}")
                            if r.get("detalle_infusion"):
                                info_container.caption(f"Indicacion complementaria: {r.get('detalle_infusion')}")
                        if r.get("firma_b64"):
                            try:
                                info_container.image(base64.b64decode(r["firma_b64"]), caption="Firma medica registrada", width=200)
                            except Exception as e:

                                from core.app_logging import log_event

                                log_event('recetas_error', f'Error: {e}')
                        if r.get("adjunto_papel_b64"):
                            try:
                                action_container.download_button(
                                    "Descargar orden adjunta",
                                    data=base64.b64decode(r["adjunto_papel_b64"]),
                                    file_name=r.get("adjunto_papel_nombre", "indicacion_medica.pdf"),
                                    mime=r.get("adjunto_papel_tipo", "application/octet-stream"),
                                    key=f"adj_papel_btn_{idx}",
                                    width="stretch",
                                )
                            except Exception:
                                info_container.caption("No se pudo preparar el adjunto cargado.")
                        if estado_actual != "Activa":
                            info_container.error(
                                f"Estado: {estado_actual.upper()} | Fecha: {r.get('fecha_suspension', 'S/D')} | "
                                f"Profesional: {r.get('profesional_estado', 'S/D')}"
                            )
                            if r.get("motivo_estado"):
                                info_container.caption(f"Motivo: {r.get('motivo_estado')}")
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
                            action_container.download_button(
                                "Descargar PDF legal",
                                data=pdf_bytes,
                                file_name=nombre_arch,
                                mime="application/pdf",
                                key=f"pdf_rec_btn_{idx}",
                                width="stretch",
                            )
        else:
            st.caption("Historial diferido para mejorar velocidad en telefonos viejos. Activalo solo si necesitas revisar indicaciones anteriores.")
