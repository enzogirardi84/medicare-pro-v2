"""Bloque UI de administración del turno, cortina MAR y gestión de indicaciones.

Extraído de views/recetas.py — función render_recetas.
"""
import base64

import pandas as pd
import streamlit as st

from core.alert_toasts import queue_toast
from core.anticolapso import anticolapso_activo
from core.database import guardar_datos
from core.utils import (
    ahora,
    format_horarios_receta,
    obtener_horarios_receta,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
)
from views._recetas_utils import (
    estado_icono as _estado_icono,
    estado_legible as _estado_legible,
    extraer_nombre_medicacion as _extraer_nombre_medicacion,
    detalle_horario_infusion as _detalle_horario_infusion,
    firma_trazabilidad_admin as _firma_trazabilidad_admin,
    orden_horario_programado as _orden_horario_programado,
    etiqueta_receta as _etiqueta_receta,
    render_tabla_clinica as _render_tabla_clinica,
    render_dataframe_filas_tarjetas as _render_dataframe_filas_tarjetas,
    ritmo_infusion_ml_h as _ritmo_infusion_ml_h,
)
from views._recetas_mar import (
    registrar_administracion_dosis as _registrar_administracion_dosis,
    guardar_administracion_medicacion as _guardar_administracion_medicacion,
    construir_matriz_registro_24h as _construir_matriz_registro_24h,
    tabla_guardia_operativa as _tabla_guardia_operativa,
    tabla_guardia_detallada as _tabla_guardia_detallada,
    render_sabana_compacta as _render_sabana_compacta,
    render_cortina_mar_hospitalaria as _render_cortina_mar_hospitalaria,
)


def _frecuencia_visible_con_ritmo(frecuencia, ritmo):
    frecuencia_txt = str(frecuencia or "").strip()
    ritmo_txt = str(ritmo or "").strip()
    if not ritmo_txt:
        return frecuencia_txt or "S/D"
    if not frecuencia_txt:
        return ritmo_txt
    if ritmo_txt.lower() in frecuencia_txt.lower() or "ml/h" in frecuencia_txt.lower():
        return frecuencia_txt
    if frecuencia_txt.lower().startswith("infusion continua"):
        return f"{frecuencia_txt} a {ritmo_txt}"
    return f"{frecuencia_txt} | {ritmo_txt}"


def render_administracion_turno(
    paciente_sel, mi_empresa, user, nombre_usuario, es_movil,
    recs_activas, admin_hoy, fecha_hoy, puede_registrar_dosis, puede_cambiar_estado,
):
    st.subheader("Administración del turno")
    limite_guardia = seleccionar_limite_registros(
        "Indicaciones activas visibles", len(recs_activas),
        key=f"recetas_guardia_limite_{paciente_sel}", default=12, opciones=(6, 12, 20, 30, 40),
    )
    recs_guardia = recs_activas[:limite_guardia]
    if len(recs_activas) > len(recs_guardia):
        st.caption(f"Se muestran {len(recs_guardia)} de {len(recs_activas)} indicaciones activas.")

    plan_dia = []
    sabana_resumen = []
    for r in recs_guardia:
        med_texto = str(r.get("med", "") or "")
        partes = med_texto.split(" | ")
        nombre = _extraer_nombre_medicacion(med_texto)
        via_texto = partes[1].replace("Via: ", "") if len(partes) > 1 and "Via:" in partes[1] else r.get("via", "")
        frecuencia_texto = str(r.get("frecuencia") or (partes[2] if len(partes) > 2 else "") or "").strip()
        frecuencia_resumen = _frecuencia_visible_con_ritmo(frecuencia_texto, _ritmo_infusion_ml_h(r))
        horarios = obtener_horarios_receta(r)
        horarios_legibles = format_horarios_receta(r)
        sabana_resumen.append({
            "Medicamento": nombre, "Via": via_texto or "S/D",
            "Frecuencia": frecuencia_resumen, "Horarios": horarios_legibles,
            "Estado": r.get("estado_receta", "Activa"),
        })
        if horarios:
            for horario in horarios:
                admin_reg = next(
                    (a for a in admin_hoy if a.get("med") == nombre
                     and (a.get("horario_programado") == horario or a.get("hora") == horario)),
                    None,
                )
                estado_actual = admin_reg.get("estado", "Pendiente") if admin_reg else "Pendiente"
                es_inf = r.get("tipo_indicacion") == "Infusion / hidratacion"
                frecuencia_visible = _frecuencia_visible_con_ritmo(frecuencia_texto or "S/D", _ritmo_infusion_ml_h(r, horario))
                plan_dia.append({
                    "OK": _estado_icono(estado_actual), "Hora programada": horario,
                    "Hora realizada": admin_reg.get("hora", "") if admin_reg else "",
                    "Medicamento": nombre, "Detalle / velocidad": _detalle_horario_infusion(r, horario),
                    "Via": via_texto or "S/D", "Frecuencia": frecuencia_visible,
                    "Estado": _estado_legible(estado_actual),
                    "Observacion": admin_reg.get("motivo", "") if admin_reg else "",
                    "Registrado por": _firma_trazabilidad_admin(admin_reg) if admin_reg else "",
                    "Solucion": r.get("solucion", "") if es_inf else "",
                    "Volumen_ml": r.get("volumen_ml", "") if es_inf else "",
                    "Velocidad_ml_h": r.get("velocidad_ml_h", "") if es_inf else "",
                })
        else:
            admin_reg = next((a for a in admin_hoy if a.get("med") == nombre), None)
            estado_actual = admin_reg.get("estado", "Pendiente") if admin_reg else "Pendiente"
            es_inf = r.get("tipo_indicacion") == "Infusion / hidratacion"
            frecuencia_visible = _frecuencia_visible_con_ritmo(frecuencia_texto or "A demanda", _ritmo_infusion_ml_h(r))
            plan_dia.append({
                "OK": _estado_icono(estado_actual), "Hora programada": "A demanda",
                "Hora realizada": admin_reg.get("hora", "") if admin_reg else "",
                "Medicamento": nombre, "Detalle / velocidad": _detalle_horario_infusion(r, ""),
                "Via": via_texto or "S/D", "Frecuencia": frecuencia_visible,
                "Estado": _estado_legible(estado_actual),
                "Observacion": admin_reg.get("motivo", "") if admin_reg else "",
                "Registrado por": _firma_trazabilidad_admin(admin_reg) if admin_reg else "",
                "Solucion": r.get("solucion", "") if es_inf else "",
                "Volumen_ml": r.get("volumen_ml", "") if es_inf else "",
                "Velocidad_ml_h": r.get("velocidad_ml_h", "") if es_inf else "",
            })

    plan_dia_df = pd.DataFrame(plan_dia)
    if not plan_dia_df.empty:
        plan_dia_df["_orden"] = plan_dia_df["Hora programada"].apply(_orden_horario_programado)
        plan_dia_df = plan_dia_df.sort_values(by=["_orden", "Medicamento"]).drop(columns=["_orden"])
    _tabla_guardia_operativa(plan_dia_df)
    _tabla_guardia_detallada(plan_dia_df)
    sabana_resumen_df = pd.DataFrame(sabana_resumen)
    matriz_registro_rows, horas_mar, matriz_registro_map = _construir_matriz_registro_24h(plan_dia_df)

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
    _tiene_estado = not plan_dia_df.empty and "Estado" in plan_dia_df.columns
    realizadas_count = int((plan_dia_df["Estado"] == "Realizada").sum()) if _tiene_estado else 0
    no_realizadas_count = (
        int(plan_dia_df["Estado"].astype(str).str.contains("No realizada", case=False, na=False).sum())
        if _tiene_estado else 0
    )
    pendientes_count = int((plan_dia_df["Estado"] == "Pendiente").sum()) if _tiene_estado else 0
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
        horizontal=True, index=0, key=f"recetas_vista_guardia_{paciente_sel}",
    )
    if vista_guardia == "Tarjetas (alternativa)":
        _render_sabana_compacta(plan_dia_df, paciente_sel, mi_empresa, user, fecha_hoy, puede_registrar_dosis)

    if puede_registrar_dosis and matriz_registro_rows:
        columnas_mar = ["Medicacion", "Via", "Frecuencia"] + horas_mar + ["A demanda"]
        matriz_registro_df = pd.DataFrame(matriz_registro_rows)[columnas_mar]
        estado_celda_opciones = ["⬜", "🟨 Pendiente", "🟩 Realizada", "🟥 No realizada"]
        for hora_col in horas_mar + ["A demanda"]:
            matriz_registro_df[hora_col] = (
                matriz_registro_df[hora_col].astype(str)
                .replace({"": "⬜", "Pendiente": "🟨 Pendiente", "Realizada": "🟩 Realizada", "No realizada": "🟥 No realizada"})
            )
        column_config = {
            "Medicacion": st.column_config.TextColumn("Medicacion", width="large"),
            "Via": st.column_config.TextColumn("Via", width="small"),
            "Frecuencia": st.column_config.TextColumn("Frecuencia", width="small"),
        }
        st.markdown("⬜ **Sin horario/celda vacía** · 🟩 **Realizada** · 🟥 **No realizada** (requiere motivo) · 🟨 **Pendiente**")
        for hora_col in horas_mar + ["A demanda"]:
            column_config[hora_col] = st.column_config.SelectboxColumn(
                hora_col, options=estado_celda_opciones, required=False, width="small",
            )
        editor_mar_df = st.data_editor(
            matriz_registro_df, hide_index=True, use_container_width=True,
            disabled=["Medicacion", "Via", "Frecuencia"], column_config=column_config,
            key=f"matriz_mar_editor_{paciente_sel}_{fecha_hoy}",
        )
        motivo_no_realizada = st.text_input(
            "Motivo clínico para celdas en rojo (No realizada)",
            placeholder="Ej. Paciente ausente, rechazo, ayuno, orden médica...",
            key=f"motivo_no_realizada_mar_{paciente_sel}_{fecha_hoy}",
        )
        if st.button("Guardar estados de cortina", use_container_width=True, key=f"guardar_mar_{paciente_sel}_{fecha_hoy}"):
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
                                paciente_sel, mi_empresa, user, nombre_med, fecha_hoy, horario_sel, "Realizada",
                            )
                        elif nuevo_valor == "🟥 No realizada":
                            if not str(motivo_no_realizada or "").strip():
                                requiere_motivo = True
                                continue
                            _registrar_administracion_dosis(
                                paciente_sel, mi_empresa, user, fecha_hoy, nombre_med, horario_sel,
                                "No realizada / Suspendida", str(motivo_no_realizada or "").strip(), hora_real_admin=None,
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
            df_plan_visible = pd.DataFrame({
                "Hora": plan_dia_df["Hora programada"],
                "Medicacion": plan_dia_df["Medicamento"],
                "Indicacion": plan_dia_df.apply(
                    lambda fila: " | ".join([
                        str(fila.get("Solucion", "") or "").strip(),
                        f"{str(fila.get('Volumen_ml', '') or '').strip()} ml" if str(fila.get('Volumen_ml', '') or '').strip() else "",
                        f"{str(fila.get('Velocidad_ml_h', '') or '').strip()} ml/h" if str(fila.get('Velocidad_ml_h', '') or '').strip() else "",
                        str(fila.get("Detalle / velocidad", "") or "").strip(),
                    ]).strip(" |"), axis=1,
                ),
                "Via / Frecuencia": plan_dia_df.apply(
                    lambda fila: " | ".join([
                        str(fila.get("Via", "") or "").strip(),
                        str(fila.get("Frecuencia", "") or "").strip(),
                    ]).strip(" |"), axis=1,
                ),
                "Estado": plan_dia_df["Estado"], "Hora real": plan_dia_df["Hora realizada"],
                "Observacion": plan_dia_df["Observacion"], "Registrado por": plan_dia_df["Registrado por"],
            })
            mostrar_tabla_planilla = st.checkbox("Usar tabla ancha", value=False, key=f"mostrar_tabla_plan_{paciente_sel}_{fecha_hoy}")
            if mostrar_tabla_planilla:
                _render_tabla_clinica(df_plan_visible, key=f"plan_{paciente_sel}",
                    max_height=300 if es_movil else (420 if not anticolapso_activo() else 320), sticky_first_col=False)
            else:
                _h = None if (es_movil and len(df_plan_visible) <= 4) else (280 if es_movil else (320 if anticolapso_activo() else 480))
                with st.container(height=_h):
                    _render_dataframe_filas_tarjetas(df_plan_visible)

    if plan_hidratacion_rows:
        st.markdown('<h4 class="mc-rx-table-zone-title">Plan de hidratación parenteral</h4>', unsafe_allow_html=True)
        _render_tabla_clinica(pd.DataFrame(plan_hidratacion_rows), key=f"hidra_{paciente_sel}",
            max_height=240 if es_movil else 320, sticky_first_col=False)

    if sabana_resumen:
        with st.expander("Ver resumen por indicación (opcional)", expanded=False):
            _render_tabla_clinica(pd.DataFrame(sabana_resumen), key=f"resumen_{paciente_sel}",
                max_height=220 if es_movil else 260, sticky_first_col=False)

    if puede_registrar_dosis:
        if es_movil or vista_guardia == "Tarjetas (alternativa)":
            registro_container = st.expander("Registro manual / no realizada / otro horario", expanded=False)
        else:
            registro_container = st.container()
        with registro_container:
            st.markdown("#### Registro manual")
            with st.form("form_registro_dosis", clear_on_submit=True):
                opciones_recetas = list(range(len(recs_activas)))
                if es_movil:
                    receta_idx = st.selectbox("Medicacion a registrar", opciones_recetas,
                        format_func=lambda idx: _etiqueta_receta(recs_activas[idx]))
                else:
                    c_med, c_hora = st.columns([2, 1])
                    receta_idx = c_med.selectbox("Medicacion a registrar", opciones_recetas,
                        format_func=lambda idx: _etiqueta_receta(recs_activas[idx]))
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
                    hora_sel = st.selectbox("Horario programado", opciones_hora or ["A demanda"], index=idx_hora if opciones_hora else 0)
                else:
                    hora_sel = c_hora.selectbox("Horario programado", opciones_hora or ["A demanda"], index=idx_hora if opciones_hora else 0)
                estado_sel = st.radio("Estado", ["Realizada", "No realizada / Suspendida"], horizontal=True)
                hora_real_manual = st.text_input(
                    "Hora real de administración o constancia (HH:MM, opcional)",
                    placeholder="Vacío = hora actual del servidor",
                )
                justificacion = st.text_input("Justificación clínica (obligatoria si no realizada)")
                if st.form_submit_button("Guardar registro", use_container_width=True):
                    nombre_med = _extraer_nombre_medicacion(receta_actual.get("med", ""))
                    if _registrar_administracion_dosis(
                        paciente_sel, mi_empresa, user, fecha_hoy, nombre_med, hora_sel,
                        estado_sel, justificacion, hora_real_admin=hora_real_manual.strip() or None,
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
                <p class="mc-rx-section-sub">Suspender o modificar con motivo explícito; cada cambio queda auditado.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        opciones_recetas = list(range(len(recs_activas)))
        if es_movil:
            receta_idx = st.selectbox("Seleccionar indicacion", opciones_recetas,
                format_func=lambda idx: _etiqueta_receta(recs_activas[idx]),
                key=f"recetas_editar_sel_{paciente_sel}")
        else:
            c_ed1, c_ed2 = st.columns([3, 2])
            receta_idx = c_ed1.selectbox("Seleccionar indicacion", opciones_recetas,
                format_func=lambda idx: _etiqueta_receta(recs_activas[idx]),
                key=f"recetas_editar_sel_{paciente_sel}")
        receta_objetivo = recs_activas[receta_idx]
        if es_movil:
            accion_receta = st.selectbox("Accion", ["Suspender / Anular", "Editar indicacion"])
        else:
            accion_receta = c_ed2.selectbox("Accion", ["Suspender / Anular", "Editar indicacion"])
        nuevo_texto_receta = ""
        motivo_cambio = st.text_input("Motivo medico / legal del cambio", key="motivo_cambio_receta")
        if accion_receta == "Editar indicacion":
            nuevo_texto_receta = st.text_input("Modificar detalle", value=receta_objetivo.get("med", ""))
        if st.button("Aplicar cambios", use_container_width=True):
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
                    registrar_auditoria_legal("Medicacion", paciente_sel, "Indicacion suspendida",
                        user.get("nombre", ""), user.get("matricula", ""),
                        f"{r.get('med', '')} | Motivo: {motivo_cambio.strip()}")
                    cambio_aplicado = True
                elif accion_receta == "Editar indicacion":
                    r["estado_receta"] = "Modificada"
                    r["estado_clinico"] = "Modificada"
                    r["fecha_suspension"] = ahora().strftime("%d/%m/%Y %H:%M:%S")
                    r["fecha_estado"] = r["fecha_suspension"]
                    r["profesional_estado"] = nombre_usuario
                    r["matricula_estado"] = user.get("matricula", "")
                    r["motivo_estado"] = motivo_cambio.strip()
                    st.session_state.setdefault("indicaciones_db", [])
                    st.session_state["indicaciones_db"].append({
                        "paciente": paciente_sel, "med": nuevo_texto_receta.strip(),
                        "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                        "dias_duracion": r.get("dias_duracion", 7),
                        "medico_nombre": r.get("medico_nombre", ""),
                        "medico_matricula": r.get("medico_matricula", ""),
                        "firma_b64": r.get("firma_b64", ""), "firmado_por": nombre_usuario,
                        "estado_clinico": "Activa", "estado_receta": "Activa",
                        "frecuencia": r.get("frecuencia", ""), "hora_inicio": r.get("hora_inicio", ""),
                        "horarios_programados": r.get("horarios_programados", []),
                        "fecha_estado": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                        "profesional_estado": nombre_usuario, "matricula_estado": user.get("matricula", ""),
                        "motivo_estado": f"Reemplaza indicacion previa. Motivo: {motivo_cambio.strip()}".strip(),
                        "origen_registro": "Prescripcion digital", "empresa": r.get("empresa", mi_empresa),
                    })
                    from core.database import _trim_db_list
                    _trim_db_list("indicaciones_db", 500)
                    registrar_auditoria_legal("Medicacion", paciente_sel, "Indicacion modificada",
                        user.get("nombre", ""), user.get("matricula", ""),
                        f"Anterior: {r.get('med', '')} | Nueva: {nuevo_texto_receta.strip()} | Motivo: {motivo_cambio.strip()}")
                    cambio_aplicado = True
            if cambio_aplicado:
                st.session_state["_rx_sql_invalidar"] = True
                guardar_datos(spinner=True)
                st.rerun()
    else:
        st.caption("La suspension o modificacion de indicaciones queda reservada a medico, coordinacion o administracion con acceso total.")


def render_historial_prescripciones(paciente_sel, mi_empresa, user, es_movil, recs_todas):
    st.divider()
    if not recs_todas:
        return
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
        "Cargar historial completo de prescripciones", value=False,
        key=f"mostrar_historial_recetas_{paciente_sel}",
    )
    if not mostrar_historial:
        st.caption("Historial diferido para mejorar velocidad en telefonos viejos. Activalo solo si necesitas revisar indicaciones anteriores.")
        return

    from core.clinical_exports import build_prescription_pdf_bytes
    from views._recetas_utils import FPDF_DISPONIBLE

    limite_hist = seleccionar_limite_registros(
        "Prescripciones a mostrar", len(recs_todas),
        key=f"limite_recetas_hist_{paciente_sel}", default=15, opciones=(10, 15, 20, 30, 50, 80),
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
                from core.utils import format_horarios_receta
                info_container.caption(f"Horarios: {format_horarios_receta(r)}")
                if r.get("tipo_indicacion") == "Infusion / hidratacion":
                    detalle_inf = []
                    if r.get("solucion"):
                        sol_vol = f"💧 {r.get('solucion')}"
                        if r.get("volumen_ml") not in ("", None, 0):
                            sol_vol += f" {r.get('volumen_ml')} ml"
                        detalle_inf.append(sol_vol)
                    if r.get("velocidad_ml_h") not in ("", None):
                        detalle_inf.append(f"Velocidad: {r.get('velocidad_ml_h')} ml/h")
                    if r.get("alternar_con"):
                        detalle_inf.append(f"Alternar con: {r.get('alternar_con')}")
                    if detalle_inf:
                        info_container.caption(" | ".join(detalle_inf))
                    from views._recetas_utils import resumen_plan_hidratacion as _resumen_plan_hidratacion
                    if r.get("plan_hidratacion"):
                        info_container.caption(f"Plan de hidratacion: {_resumen_plan_hidratacion(r.get('plan_hidratacion', []))}")
                    if r.get("detalle_infusion"):
                        info_container.caption(f"Indicacion complementaria: {r.get('detalle_infusion')}")
                if r.get("firma_b64"):
                    try:
                        info_container.image(base64.b64decode(r["firma_b64"]), caption="Firma medica registrada", width=200)
                    except Exception as e:
                        from core.app_logging import log_event
                        log_event("recetas_error", f"Error: {e}")
                if r.get("adjunto_papel_b64"):
                    try:
                        action_container.download_button(
                            "Descargar orden adjunta", data=base64.b64decode(r["adjunto_papel_b64"]),
                            file_name=r.get("adjunto_papel_nombre", "indicacion_medica.pdf"),
                            mime=r.get("adjunto_papel_tipo", "application/octet-stream"),
                            key=f"adj_papel_btn_{idx}", use_container_width=True,
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
                        st.session_state, paciente_sel, mi_empresa, r,
                        {"nombre": r.get("medico_nombre", user.get("nombre", "")), "matricula": r.get("medico_matricula", "")},
                    )
                    estado_arch = (r.get("estado_receta") or "Activa").replace(" ", "_")
                    nombre_arch = (
                        f"Receta_Legal_{paciente_sel.split(' - ')[0].replace(' ', '_')}_"
                        f"{r.get('fecha', '')[:10].replace('/','')}_{ estado_arch}.pdf"
                    )
                    action_container.download_button(
                        "Descargar PDF legal", data=pdf_bytes, file_name=nombre_arch,
                        mime="application/pdf", key=f"pdf_rec_btn_{idx}", use_container_width=True,
                    )
