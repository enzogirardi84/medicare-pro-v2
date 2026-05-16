"""Bloque UI de nueva prescripción médica e indicación en papel.

Extraído de views/recetas.py — función render_recetas.
"""
import base64
from datetime import time as dt_time

import streamlit as st

from core.alert_toasts import queue_toast
from core.database import guardar_datos
from core.utils import (
    ahora,
    firma_a_base64,
    horarios_programados_desde_frecuencia,
    obtener_config_firma,
    registrar_auditoria_legal,
)
from views._recetas_indicaciones import construir_texto_indicacion as _construir_texto_indicacion
from views._recetas_utils import archivo_a_base64 as _archivo_a_base64

try:
    from streamlit_drawable_canvas import st_canvas
    CANVAS_DISPONIBLE = True
except ImportError:
    CANVAS_DISPONIBLE = False


_FRECUENCIAS = [
    "Cada 1 hora", "Cada 2 horas", "Cada 4 horas", "Cada 6 horas",
    "Cada 8 horas", "Cada 12 horas", "Cada 24 horas", "Dosis unica", "Segun necesidad",
]
_VIAS = ["Via Oral", "Via Endovenosa", "Via Intramuscular", "Via Subcutanea",
         "Via Topica", "Via Inhalatoria", "Otra"]
_SOLUCIONES = ["Dextrosa 5%", "Fisiologico 0.9%", "Ringer lactato", "Mixta", "Otra"]


def render_nueva_prescripcion(paciente_sel, mi_empresa, user, rol, nombre_usuario, es_movil, vademecum_base):
    st.subheader("Nueva prescripción médica")
    with st.container(border=True):
        tipo_indicacion = st.radio(
            "Tipo de indicacion",
            ["Medicacion", "Infusion / hidratacion"],
            horizontal=True,
            key="tipo_indicacion_receta",
        )
        med_vademecum = "-- Seleccionar del vademecum --"
        med_manual = solucion = detalle_infusion = alternar_con = frecuencia = ""
        volumen_ml = 0
        velocidad_ml_h = None
        plan_hidratacion = []

        if tipo_indicacion == "Medicacion":
            if es_movil:
                med_vademecum = st.selectbox("Medicamento", ["-- Seleccionar del vademecum --"] + vademecum_base)
                med_manual = st.text_input("O escribir manualmente")
                via = st.selectbox("Via de administracion", _VIAS)
                frecuencia = st.selectbox("Frecuencia", _FRECUENCIAS)
                dias = st.number_input("Dias", min_value=1, max_value=90, value=7)
            else:
                c1, c2 = st.columns([3, 1])
                med_vademecum = c1.selectbox("Medicamento", ["-- Seleccionar del vademecum --"] + vademecum_base)
                med_manual = c2.text_input("O escribir manualmente")
                col3, col4, col5 = st.columns([2, 2, 1])
                via = col3.selectbox("Via de administracion", _VIAS)
                frecuencia = col4.selectbox("Frecuencia", _FRECUENCIAS)
                dias = col5.number_input("Dias", min_value=1, max_value=90, value=7)
            hora_inicio = st.time_input("Hora inicial de administracion", value=dt_time(8, 0), key="hora_inicio_receta")
            horarios_sugeridos = horarios_programados_desde_frecuencia(frecuencia, hora_inicio.strftime("%H:%M"))
            if horarios_sugeridos:
                st.caption(f"Horarios sugeridos para la guardia: {' | '.join(horarios_sugeridos)}")
            else:
                st.caption("Indicacion sin horario fijo. Se mostrara como dosis unica o a demanda segun la frecuencia.")
        else:
            via = "Via Endovenosa"
            frecuencia = "Infusion continua"
            if es_movil:
                solucion = st.selectbox("Solucion principal", _SOLUCIONES, key="solucion_receta")
                volumen_ml = st.number_input("Volumen total (ml)", min_value=0, step=50, value=500, key="volumen_receta")
                dias = st.number_input("Dias", min_value=1, max_value=90, value=1, key="dias_infusion_receta")
                velocidad_ml_h = st.number_input("Velocidad (ml/h)", min_value=0.0, step=1.0, value=21.0, key="velocidad_receta")
                hora_inicio = st.time_input("Hora inicial", value=dt_time(8, 0), key="hora_inicio_infusion_receta")
            else:
                c1, c2, c3 = st.columns([2, 1, 1])
                solucion = c1.selectbox("Solucion principal", _SOLUCIONES, key="solucion_receta")
                volumen_ml = c2.number_input("Volumen total (ml)", min_value=0, step=50, value=500, key="volumen_receta")
                dias = c3.number_input("Dias", min_value=1, max_value=90, value=1, key="dias_infusion_receta")
                c4, c5 = st.columns([1, 2])
                velocidad_ml_h = c4.number_input("Velocidad (ml/h)", min_value=0.0, step=1.0, value=21.0, key="velocidad_receta")
                hora_inicio = c5.time_input("Hora inicial", value=dt_time(8, 0), key="hora_inicio_infusion_receta")
            horarios_sugeridos = [hora_inicio.strftime("%H:%M")]
            detalle_infusion = st.text_area(
                "Notas / evolucion del medico (opcional)",
                placeholder="Si quiere agregar alguna indicacion adicional o detalle sobre el plan, escribalo aqui.",
                key="detalle_infusion_receta",
                height=80,
            )
            st.caption(f"Horario visible en la sabana diaria: {hora_inicio.strftime('%H:%M')} — {int(velocidad_ml_h) if velocidad_ml_h else '?'} ml/h")

        if es_movil:
            medico_nombre = st.text_input("Nombre del medico", value=user.get("nombre", ""))
            medico_matricula = st.text_input("Matricula profesional")
        else:
            col_m1, col_m2 = st.columns(2)
            medico_nombre = col_m1.text_input("Nombre del medico", value=user.get("nombre", ""))
            medico_matricula = col_m2.text_input("Matricula profesional")

        st.divider()
        adjunto_papel = st.file_uploader(
            "📷 Adjuntar foto de la orden en papel (opcional)",
            type=["pdf", "png", "jpg", "jpeg"],
            key="adjunto_receta",
            help="Si tenés la indicación escrita a mano o impresa por el médico, subí la foto para respaldo legal.",
        )

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

        if st.button("Guardar prescripcion medica", width='stretch', type="primary"):
            med_final = med_manual.strip().title() if med_manual.strip() else med_vademecum
            if tipo_indicacion == "Medicacion" and (not med_final or med_final == "-- Seleccionar del vademecum --"):
                st.error("Debe seleccionar o escribir un medicamento.")
            elif tipo_indicacion == "Infusion / hidratacion" and not solucion.strip():
                st.error("Debe indicar la solucion principal.")
            elif not medico_matricula.strip():
                st.error("Debe ingresar la matricula del medico.")
            else:
                firma_b64 = firma_a_base64(
                    canvas_image_data=firma_canvas.image_data if firma_canvas is not None else None,
                    uploaded_file=firma_subida,
                )
                adjunto_b64 = adjunto_nombre = adjunto_tipo = ""
                if adjunto_papel is not None:
                    adjunto_b64, adjunto_nombre, adjunto_tipo = _archivo_a_base64(adjunto_papel)
                texto_receta = _construir_texto_indicacion(
                    tipo_indicacion=tipo_indicacion, med_final=med_final, via=via,
                    frecuencia=frecuencia, dias=dias, solucion=solucion, volumen_ml=volumen_ml,
                    velocidad_ml_h=velocidad_ml_h, alternar_con=alternar_con,
                    detalle_infusion=detalle_infusion, plan_hidratacion=plan_hidratacion,
                )
                from core.database import guardar_json_db
                guardar_json_db("indicaciones_db", {
                    "paciente": paciente_sel, "med": texto_receta,
                    "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"), "dias_duracion": dias,
                    "medico_nombre": medico_nombre.strip(), "medico_matricula": medico_matricula.strip(),
                    "firma_b64": firma_b64, "firmado_por": nombre_usuario,
                    "estado_clinico": "Activa", "estado_receta": "Activa",
                    "frecuencia": frecuencia, "hora_inicio": hora_inicio.strftime("%H:%M"),
                    "horarios_programados": horarios_sugeridos, "tipo_indicacion": tipo_indicacion,
                    "solucion": solucion, "volumen_ml": volumen_ml, "velocidad_ml_h": velocidad_ml_h,
                    "alternar_con": alternar_con, "detalle_infusion": detalle_infusion,
                    "plan_hidratacion": plan_hidratacion,
                    "fecha_estado": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                    "profesional_estado": nombre_usuario, "matricula_estado": medico_matricula.strip(),
                    "origen_registro": "Indicacion medica en papel" if adjunto_papel else "Prescripcion digital",
                    "adjunto_papel_b64": adjunto_b64, "adjunto_papel_nombre": adjunto_nombre,
                    "adjunto_papel_tipo": adjunto_tipo, "empresa": mi_empresa,
                }, spinner=True)
                registrar_auditoria_legal(
                    "Medicacion", paciente_sel, "Indicacion medica registrada",
                    medico_nombre.strip() or user.get("nombre", ""), medico_matricula.strip(), texto_receta,
                )
                from core.nextgen_sync import sync_receta_to_sql
                sync_receta_to_sql(paciente_sel, med_final, via, frecuencia, tipo_indicacion, {
                    "dias_duracion": dias, "medico_nombre": medico_nombre.strip(),
                    "medico_matricula": medico_matricula.strip(), "firma_b64": firma_b64,
                    "hora_inicio": hora_inicio.strftime("%H:%M"), "horarios_programados": horarios_sugeridos,
                    "solucion": solucion, "volumen_ml": volumen_ml, "velocidad_ml_h": velocidad_ml_h,
                    "alternar_con": alternar_con, "detalle_infusion": detalle_infusion, "plan_hidratacion": plan_hidratacion,
                })
                st.session_state["_rx_sql_invalidar"] = True
                queue_toast(f"Prescripcion de {med_final} guardada{' con adjunto de papel' if adjunto_papel else ''}.")
                st.rerun()



