"""MAR hospitalaria (Medication Administration Record), cortina y sábana compacta.

Extraído de views/recetas.py para mantenerlo bajo las 300 líneas.
Funciones públicas usadas desde recetas.py:
    registrar_administracion_dosis, guardar_administracion_medicacion,
    construir_matriz_registro_24h, tabla_guardia_operativa, tabla_guardia_detallada,
    render_cortina_mar_hospitalaria, render_bloque_cortina_medicacion, render_sabana_compacta,
    render_marco_clinico_cortina
"""
import re

import streamlit as st

from core.alert_toasts import queue_toast
from core.database import guardar_datos
from core.utils import ahora, registrar_auditoria_legal
from views._recetas_utils import (
    hora_real_para_registro,
    nombre_usuario,
    parse_hora_hhmm,
    texto_corto,
)

try:
    import pandas as pd
except ImportError:
    pd = None


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _default_hora_real_cortina(hp_raw):
    hp = str(hp_raw or "").strip()
    if hp.lower() == "a demanda" or not hp:
        return ahora().strftime("%H:%M")
    norm = parse_hora_hhmm(hp)
    return norm if norm else hp


def _cortina_mar_key_slug(paciente_sel: str, fecha_hoy: str) -> str:
    p = re.sub(r"[^\w\-]", "_", str(paciente_sel))[:44]
    f = str(fecha_hoy).replace("/", "_").replace(" ", "_")
    return f"{p}_{f}"


# ---------------------------------------------------------------------------
# Registro de administración
# ---------------------------------------------------------------------------

def registrar_administracion_dosis(
    paciente_sel, mi_empresa, user, fecha_hoy,
    nombre_med, horario_programado_slot, estado_sel, justificacion,
    *, hora_real_admin=None,
):
    if "No realizada" in estado_sel and not justificacion.strip():
        st.error("Es obligatorio justificar por qué no se administró la dosis (documentación clínica exigible).")
        return False

    hora_str, err_h = hora_real_para_registro(hora_real_admin)
    if err_h:
        st.error(err_h)
        return False

    slot = str(horario_programado_slot or "").strip()
    st.session_state["administracion_med_db"] = [
        a for a in st.session_state.get("administracion_med_db", [])
        if not (
            a.get("paciente") == paciente_sel
            and a.get("fecha") == fecha_hoy
            and a.get("med") == nombre_med
            and str(a.get("horario_programado", "") or "").strip() == slot
        )
    ]
    ts_evento = ahora()
    mat_prof = str(user.get("matricula", "") or "").strip()
    login_ref = str(user.get("usuario_login", user.get("usuario", "")) or "").strip()

    from core.database import guardar_json_db
    guardar_json_db("administracion_med_db", {
        "paciente": paciente_sel,
        "med": nombre_med,
        "fecha": fecha_hoy,
        "hora": hora_str,
        "horario_programado": horario_programado_slot,
        "estado": estado_sel,
        "motivo": justificacion.strip() if "No realizada" in estado_sel else "",
        "firma": nombre_usuario(user),
        "matricula_profesional": mat_prof,
        "usuario_login": login_ref,
        "registro_iso": ts_evento.isoformat(timespec="seconds"),
        "registro_fecha_hora": ts_evento.strftime("%d/%m/%Y %H:%M:%S"),
        "empresa": mi_empresa,
    }, spinner=True)
    detalle_audit = (
        f"{nombre_med} | Programada: {slot} | Hora administración/registro: {hora_str} | Estado: {estado_sel}"
    )
    if "No realizada" in estado_sel and justificacion.strip():
        detalle_audit += f" | Justificación: {justificacion.strip()[:200]}"
    registrar_auditoria_legal(
        "Medicacion", paciente_sel, "Registro MAR / administración de medicación",
        user.get("nombre", ""), user.get("matricula", ""), detalle_audit,
        referencia=f"MAR|{fecha_hoy}|{slot}|{nombre_med[:48]}",
        extra={"horario_programado": slot, "hora_clinica": hora_str, "estado_administracion": estado_sel, "modulo_ui": "Recetas"},
        empresa=mi_empresa,
        usuario=user if isinstance(user, dict) else None,
        modulo="Recetas / MAR",
        criticidad="alta",
    )
    from core.nextgen_sync import sync_administracion_to_sql
    sync_administracion_to_sql(
        paciente_sel, nombre_med, slot, estado_sel,
        justificacion.strip() if "No realizada" in estado_sel else "",
        {"medicamento": nombre_med, "hora_real_administracion": hora_str,
         "firma": nombre_usuario(user), "matricula_profesional": mat_prof, "usuario_login": login_ref},
    )
    return True


def guardar_administracion_medicacion(
    paciente_sel, mi_empresa, user, nombre_med, fecha_hoy, horario_sel, estado_sel, *, hora_real_admin=None
):
    return registrar_administracion_dosis(
        paciente_sel, mi_empresa, user, fecha_hoy,
        nombre_med, horario_sel, estado_sel, "", hora_real_admin=hora_real_admin,
    )


# ---------------------------------------------------------------------------
# Construcción de matrices de datos para las tablas
# ---------------------------------------------------------------------------

def construir_matriz_registro_24h(plan_dia_df):
    horas_mar = [f"{h:02d}:00" for h in range(24)]
    if plan_dia_df.empty:
        return [], horas_mar, {}

    matriz_registro_rows = []
    matriz_registro_map = {}
    row_by_key = {}

    for _, r in plan_dia_df.iterrows():
        med = str(r.get("Medicamento", "") or "").strip()
        via = str(r.get("Via", "") or "").strip() or "S/D"
        freq = str(r.get("Frecuencia", "") or "").strip() or "S/D"
        detalle = str(r.get("Detalle / velocidad", "") or "").strip()
        hp = str(r.get("Hora programada", "") or "").strip()
        estado_txt = str(r.get("Estado", "") or "").strip().lower()
        if "realizada" in estado_txt and "no realizada" not in estado_txt:
            estado_valor = "Realizada"
        elif "no realizada" in estado_txt or "suspendida" in estado_txt:
            estado_valor = "No realizada"
        else:
            estado_valor = "Pendiente"

        fila_key = (med, via, freq, detalle)
        if fila_key not in row_by_key:
            row_dict = {"Medicacion": med, "Via": via, "Frecuencia": freq, "Detalle": detalle}
            for h in horas_mar:
                row_dict[h] = ""
            row_dict["A demanda"] = ""
            row_by_key[fila_key] = len(matriz_registro_rows)
            matriz_registro_rows.append(row_dict)

        mat_idx = row_by_key[fila_key]
        row_dict = matriz_registro_rows[mat_idx]

        col = None
        if hp.lower() == "a demanda":
            col = "A demanda"
            valor_actual = row_dict[col]
            if not valor_actual:
                row_dict[col] = estado_valor
            elif "Pendiente" in {valor_actual, estado_valor}:
                row_dict[col] = "Pendiente"
            elif "No realizada" in {valor_actual, estado_valor}:
                row_dict[col] = "No realizada"
            else:
                row_dict[col] = "Realizada"
        else:
            partes = hp.split(":")
            if len(partes) >= 2 and str(partes[0]).strip().isdigit():
                col = f"{int(str(partes[0]).strip()) % 24:02d}:00"
                if col in row_dict:
                    valor_actual = row_dict[col]
                    if not valor_actual:
                        row_dict[col] = estado_valor
                    elif "Pendiente" in {valor_actual, estado_valor}:
                        row_dict[col] = "Pendiente"
                    elif "No realizada" in {valor_actual, estado_valor}:
                        row_dict[col] = "No realizada"
                    else:
                        row_dict[col] = "Realizada"

        if col:
            matriz_registro_map.setdefault((mat_idx, col), []).append(
                {"medicamento": med, "horario_programado": hp if hp.lower() != "a demanda" else "A demanda"}
            )

    return matriz_registro_rows, horas_mar, matriz_registro_map


def tabla_guardia_operativa(plan_dia_df):
    columnas_base = ["Hora", "Medicacion", "Indicacion", "Estado", "Registro"]
    if plan_dia_df.empty:
        return pd.DataFrame(columns=columnas_base)

    tabla = plan_dia_df.copy()
    tabla["Indicacion"] = tabla.apply(
        lambda fila: " | ".join(
            parte for parte in [
                texto_corto(fila.get("Via", ""), fallback="", max_len=18),
                texto_corto(fila.get("Frecuencia", ""), fallback="", max_len=24),
            ] if parte
        ) or "S/D",
        axis=1,
    )
    tabla["Registro"] = tabla.apply(
        lambda fila: texto_corto(fila.get("Hora realizada", ""), fallback="", max_len=12)
        if str(fila.get("Hora realizada", "")).strip()
        else texto_corto(fila.get("Registrado por", ""), fallback="Sin registro", max_len=26),
        axis=1,
    )
    tabla["Observacion corta"] = tabla["Observacion"].apply(lambda v: texto_corto(v, fallback="", max_len=32))
    columnas = ["Hora programada", "Medicamento", "Indicacion", "Estado", "Registro"]
    if tabla["Observacion corta"].astype(str).str.strip().any():
        columnas.append("Observacion corta")
    return tabla[columnas].rename(columns={"Hora programada": "Hora", "Medicamento": "Medicacion", "Observacion corta": "Obs."})


def tabla_guardia_detallada(plan_dia_df):
    columnas_base = ["Hora", "Hora real", "Medicacion", "Detalle", "Indicacion", "Estado", "Observacion", "Registrado por"]
    if plan_dia_df.empty:
        return pd.DataFrame(columns=columnas_base)

    tabla = plan_dia_df.copy()
    tabla["Indicacion"] = tabla.apply(
        lambda fila: " | ".join(
            parte for parte in [
                texto_corto(fila.get("Via", ""), fallback="", max_len=18),
                texto_corto(fila.get("Frecuencia", ""), fallback="", max_len=24),
            ] if parte
        ) or "S/D",
        axis=1,
    )
    return tabla[
        ["Hora programada", "Hora realizada", "Medicamento", "Detalle / velocidad", "Indicacion", "Estado", "Observacion", "Registrado por"]
    ].rename(columns={"Hora programada": "Hora", "Hora realizada": "Hora real", "Medicamento": "Medicacion", "Detalle / velocidad": "Detalle"})


# ---------------------------------------------------------------------------
# Renders de la cortina y sábana
# ---------------------------------------------------------------------------

def _html_cortina_resumen_visual(plan_dia_df):
    from html import escape
    chunks = [
        '<div class="mc-cortina-panel mc-cortina-panel--premium">'
        '<p class="mc-cortina-intro">Vista del turno — horario programado vs hora de administración o constancia, estado y profesional responsable (trazabilidad clínica y auditoría).</p>'
        '<div class="mc-cortina-resumen">'
    ]
    for _, r in plan_dia_df.iterrows():
        estado = str(r.get("Estado", "") or "")
        row_cls = "mc-cortina-row mc-cortina-row--pend"
        badge = '<span class="mc-cortina-badge mc-cortina-badge--pend">Pendiente</span>'
        if estado == "Realizada":
            row_cls = "mc-cortina-row mc-cortina-row--ok"
            badge = '<span class="mc-cortina-badge mc-cortina-badge--ok">Administrada</span>'
        elif "No realizada" in estado or "Suspendida" in estado:
            row_cls = "mc-cortina-row mc-cortina-row--no"
            badge = '<span class="mc-cortina-badge mc-cortina-badge--no">No administrada</span>'
        hp = escape(str(r.get("Hora programada", "") or "—"))
        hr = escape(str(r.get("Hora realizada", "") or "—"))
        med = escape(str(r.get("Medicamento", "") or "—"))
        via = escape(str(r.get("Via", "") or ""))
        freq = escape(str(r.get("Frecuencia", "") or ""))
        det = escape(str(r.get("Detalle / velocidad", "") or "").strip() or "—")
        obs = str(r.get("Observacion", "") or "").strip()
        obs_e = escape(obs) if obs else ""
        firma = escape(str(r.get("Registrado por", "") or ""))
        meta_vf = " · ".join(x for x in [via, freq] if x) or "S/D"
        obs_html = f'<div class="mc-cortina-obs"><span class="mc-cortina-obs-lbl">Justif. / obs.</span> {obs_e}</div>' if obs_e else ""
        firma_html = (
            f'<div class="mc-cortina-firma">Profesional responsable: <b>{firma}</b></div>'
            if firma
            else '<div class="mc-cortina-firma mc-cortina-firma--empty">Sin registro de profesional aún</div>'
        )
        chunks.append(
            f'<div class="{row_cls}">'
            f'<div class="mc-cortina-row-top">{badge}</div>'
            f'<div class="mc-cortina-med">{med}</div>'
            f'<div class="mc-cortina-times">Programada <b>{hp}</b> · Administración/registro <b>{hr}</b></div>'
            f'<div class="mc-cortina-meta">{escape(meta_vf)}</div>'
            f'<div class="mc-cortina-detalle">{det}</div>'
            f"{obs_html}{firma_html}</div>"
        )
    chunks.append("</div></div>")
    return "".join(chunks)


def render_marco_clinico_cortina():
    with st.expander("Seguridad del medicamento, trazabilidad y marco legal (referencia internacional)", expanded=False):
        st.markdown("""
**Cinco correctos (referencia habitual OMS / buenas prácticas hospitalarias)**  
Antes de confirmar cada administración, el equipo debería verificar de forma sistemática:

1. **Paciente correcto** — identidad acorde a la política de la institución (idealmente dos identificadores).  
2. **Medicamento correcto** — principio activo, presentación y equivalencia con la prescripción.  
3. **Dosis correcta** — incluye concentración, dilución y dispositivo de medición cuando aplica.  
4. **Vía correcta** — coherente con la indicación y el estado del paciente.  
5. **Momento correcto** — hora programada frente a hora real documentada (demoras, ayuno, procedimientos).

**Registro en este sistema**  
Cada acción queda asociada al **usuario autenticado**, **hora de registro en servidor** y, si está cargada, **matrícula profesional**, con copia en **auditoría legal** para inspecciones internas o requerimientos regulatorios.

**Valor documental**  
Las entradas forman parte de la **documentación asistencial** y deben ser **veraces y oportunas**. El cumplimiento de **leyes sanitarias, profesionales y de protección de datos personales** depende de la **normativa y protocolos de tu país o provincia** y de las políticas institucionales — este módulo no reemplaza asesoramiento jurídico ni auditoría externa.

**Alta vigilancia**  
Medicación de riesgo (anticoagulantes, insulina, opioides, electrolitos IV, etc.): seguí **protocolos locales** (doble verificación, límites de dosis, observación).
        """)


def _render_cortina_tildado_rapido(pendientes_base, paciente_sel, mi_empresa, user, fecha_hoy):
    if pendientes_base.empty:
        return
    st.markdown('<p class="mc-cortina-rapida-titulo">Cortina rápida — tilde solo lo que diste ahora</p>', unsafe_allow_html=True)
    st.caption("Marcá **Dada**, ajustá **Hora real** si hace falta, y guardá. Para **no realizada** usá el registro avanzado abajo.")

    rapida = pendientes_base[["Hora programada", "Medicamento", "Via", "Frecuencia"]].copy()
    rapida["Dada"] = False
    rapida["Hora_real"] = rapida["Hora programada"].map(_default_hora_real_cortina)

    ed_rap = st.data_editor(
        rapida, hide_index=True, use_container_width=True,
        disabled=["Hora programada", "Medicamento", "Via", "Frecuencia"],
        column_config={
            "Hora programada": st.column_config.TextColumn("Prog.", width="small"),
            "Medicamento": st.column_config.TextColumn("Medicación", width="medium"),
            "Via": st.column_config.TextColumn("Vía", width="small"),
            "Frecuencia": st.column_config.TextColumn("Frec.", width="small"),
            "Dada": st.column_config.CheckboxColumn("Dada", help="Solo si administraste esta dosis en esta franja.", default=False),
            "Hora_real": st.column_config.TextColumn("Hora real", max_chars=8, width="small"),
        },
        key=f"cortina_rapida_{paciente_sel}_{fecha_hoy}",
    )

    if st.button("Guardar tildes rápidos", use_container_width=True, type="primary", key=f"guardar_cortina_rapida_{paciente_sel}_{fecha_hoy}"):
        n = 0
        for _, fila in ed_rap.iterrows():
            if not bool(fila.get("Dada")):
                continue
            med = str(fila.get("Medicamento", "") or "").strip()
            slot = str(fila.get("Hora programada", "") or "").strip()
            hr = str(fila.get("Hora_real", "") or "").strip()
            if not med:
                continue
            if registrar_administracion_dosis(paciente_sel, mi_empresa, user, fecha_hoy, med, slot, "Realizada", "", hora_real_admin=hr or None):
                n += 1
        if n:
            queue_toast(f"Listo: {n} administración(es) registrada(s).")
            st.rerun()
        else:
            st.info("Tildá **Dada** en al menos una fila o usá el registro avanzado.")


def render_cortina_mar_hospitalaria(plan_dia_df, paciente_sel, mi_empresa, user, fecha_hoy):
    if plan_dia_df.empty:
        return
    from html import escape
    from core.ui_liviano import headers_sugieren_equipo_liviano

    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
    suf = _cortina_mar_key_slug(paciente_sel, fecha_hoy)
    st.markdown('<p class="mc-mar-encabezado">Planilla MAR del turno</p>', unsafe_allow_html=True)
    plan_ord = plan_dia_df.reset_index(drop=True)
    altura_mar = None if es_movil and len(plan_ord) <= 4 else (340 if es_movil else 520)
    with st.container(height=altura_mar):
        for i, (_, fila) in enumerate(plan_ord.iterrows()):
            estado = str(fila.get("Estado", "") or "").strip()
            es_pend = estado == "Pendiente"
            es_ok = estado == "Realizada"
            es_no = "No realizada" in estado or "Suspendida" in estado

            med_raw = str(fila.get("Medicamento", "") or "").strip() or "—"
            med = escape(med_raw)
            via = escape(str(fila.get("Via", "") or "S/D"))
            freq = escape(str(fila.get("Frecuencia", "") or "S/D"))
            det = escape(str(fila.get("Detalle / velocidad", "") or "").strip() or "—")
            solucion = escape(str(fila.get("Solucion", "") or "").strip())
            volumen = str(fila.get("Volumen_ml", "") or "").strip()
            velocidad = str(fila.get("Velocidad_ml_h", "") or "").strip()
            hp = escape(str(fila.get("Hora programada", "") or "—"))
            hr_reg = str(fila.get("Hora realizada", "") or "").strip()
            hr_e = escape(hr_reg if hr_reg else "—")
            firma = escape(str(fila.get("Registrado por", "") or "").strip())
            obs = str(fila.get("Observacion", "") or "").strip()
            obs_e = escape(obs) if obs else ""

            blk = "mc-mar-block"
            if es_pend:
                blk = "mc-mar-block mc-mar-block--pend"
            elif es_ok:
                blk = "mc-mar-block mc-mar-block--ok"
            elif es_no:
                blk = "mc-mar-block mc-mar-block--no"

            ritmo_inner = f"Horario programado <b>{hp}</b> · Hora administración/registro <b>{hr_e}</b>"
            if es_ok and firma:
                ritmo_inner += f' · <span class="mc-mar-firma">Profesional: {firma}</span>'
            extra_obs = f'<div class="mc-mar-chip-note"><b>Justif.</b> {obs_e}</div>' if (es_no and obs_e) else ""

            with st.container(border=True):
                if es_movil:
                    info_container = st.container()
                    action_container = st.container()
                else:
                    info_container, action_container = st.columns([4.4, 2.6])
                with info_container:
                    detalle_inf_html = ""
                    if solucion:
                        detalle_inf_html += f'<div class="mc-mar-detail">💧 <b>{solucion}</b>'
                        if volumen:
                            detalle_inf_html += f' — {volumen} ml'
                        if velocidad:
                            detalle_inf_html += f' @ {velocidad} ml/h'
                        detalle_inf_html += '</div>'
                    st.markdown(
                        f'<div class="{blk}">'
                        f'<div class="mc-mar-title">{med.upper()}</div>'
                        f'<div class="mc-mar-sub">{via} · {freq}</div>'
                        f'{detalle_inf_html}'
                        f'<div class="mc-mar-detail">{det}</div>'
                        f'<div class="mc-mar-ritmo">{ritmo_inner}</div>'
                        f"{extra_obs}</div>",
                        unsafe_allow_html=True,
                    )
                with action_container:
                    if es_pend:
                        k_hr = f"mar_hr_{suf}_{i}"
                        k_just = f"mar_just_{suf}_{i}"
                        def_h = _default_hora_real_cortina(fila.get("Hora programada"))
                        st.text_input("Hora de administración o constancia (HH:MM)", value=def_h, max_chars=8, key=k_hr,
                                      help="Hora clínica a dejar en legajo; puede diferir de la programada.")
                        st.text_input("Motivo clínico (obligatorio si no se administra)", value="", max_chars=400, key=k_just,
                                      placeholder="Ej. Paciente ausente, rechazo, ayuno, orden médica de suspensión…")
                        if es_movil:
                            b1, b2 = st.container(), st.container()
                        else:
                            b1, b2 = st.columns(2)
                        with b1:
                            if st.button("Administración realizada", key=f"mar_ok_{suf}_{i}", type="primary", use_container_width=True,
                                         help="Registra administración conforme a la indicación (queda firmado y auditado)."):
                                hr_val = str(st.session_state.get(k_hr, def_h) or "").strip() or def_h
                                if registrar_administracion_dosis(paciente_sel, mi_empresa, user, fecha_hoy, med_raw,
                                                                   str(fila.get("Hora programada", "") or "").strip(), "Realizada", "", hora_real_admin=hr_val):
                                    st.rerun()
                        with b2:
                            if st.button("No administrada / suspendida", key=f"mar_no_{suf}_{i}", use_container_width=True,
                                         help="Requiere motivo clínico documentado (trazabilidad legal)."):
                                just = str(st.session_state.get(k_just, "") or "").strip()
                                hr_val = str(st.session_state.get(k_hr, def_h) or "").strip() or def_h
                                if not just:
                                    st.error("Documentá el motivo clínico antes de registrar una omisión (requisito de historia clínica).")
                                elif registrar_administracion_dosis(paciente_sel, mi_empresa, user, fecha_hoy, med_raw,
                                                                    str(fila.get("Hora programada", "") or "").strip(), "No realizada / Suspendida", just, hora_real_admin=hr_val):
                                    st.rerun()
                    elif es_ok:
                        st.markdown('<span class="mc-mar-chip mc-mar-chip--ok">Administrada</span>', unsafe_allow_html=True)
                    elif es_no:
                        st.markdown('<span class="mc-mar-chip mc-mar-chip--no">No administrada</span>', unsafe_allow_html=True)
                    else:
                        st.caption(estado or "—")


def render_bloque_cortina_medicacion(plan_dia_df, columnas_tabla, paciente_sel, mi_empresa, user, fecha_hoy, puede_registrar_dosis):
    if plan_dia_df.empty:
        return

    pendientes_base = plan_dia_df[
        plan_dia_df["Estado"].map(lambda e: str(e or "").strip().lower() == "pendiente")
    ].copy().reset_index(drop=True)
    n_pend = len(pendientes_base)

    with st.expander(f"Cortina de medicación ({n_pend} pendientes)", expanded=False):
        st.markdown(_html_cortina_resumen_visual(plan_dia_df), unsafe_allow_html=True)
        if not puede_registrar_dosis:
            st.warning("Solo lectura: tu rol no puede registrar administración desde acá.")
            return
        if pendientes_base.empty:
            st.caption("No hay filas pendientes para registrar en esta vista.")
            return

        render_cortina_mar_hospitalaria(plan_dia_df, paciente_sel, mi_empresa, user, fecha_hoy)

        with st.expander("Tabla rápida", expanded=False):
            _render_cortina_tildado_rapido(pendientes_base, paciente_sel, mi_empresa, user, fecha_hoy)

        with st.expander("Registro avanzado", expanded=False):
            pendientes_df = pendientes_base.copy()
            pendientes_df["Accion"] = "(sin cambio)"
            pendientes_df["Hora_real"] = pendientes_df["Hora programada"].map(_default_hora_real_cortina)
            pendientes_df["Justificacion"] = ""

            _cols_ref = [c for c in columnas_tabla if c in pendientes_df.columns]
            editor_columnas = _cols_ref + ["Accion", "Hora_real", "Justificacion"]
            disabled_cols = [c for c in editor_columnas if c not in ("Accion", "Hora_real", "Justificacion")]

            editor_df = st.data_editor(
                pendientes_df[editor_columnas], hide_index=True, use_container_width=True, disabled=disabled_cols,
                column_config={
                    "Accion": st.column_config.SelectboxColumn("Acción", options=["(sin cambio)", "Realizada", "No realizada"], required=True),
                    "Hora_real": st.column_config.TextColumn("Hora real (HH:MM)", max_chars=8),
                    "Justificacion": st.column_config.TextColumn("Justificación (si no realizada)", max_chars=400),
                },
                key=f"cortina_tabla_editor_{paciente_sel}_{fecha_hoy}",
            )

            if st.button("Guardar registro avanzado (cortina)", use_container_width=True, key=f"guardar_tildes_cortina_{paciente_sel}_{fecha_hoy}"):
                registros_guardados = 0
                errores = []
                for _idx, fila in editor_df.iterrows():
                    accion = str(fila.get("Accion", "")).strip()
                    if accion in ("(sin cambio)", ""):
                        continue
                    slot = str(fila.get("Hora programada", "") or "").strip()
                    nombre_med = str(fila.get("Medicamento", "") or "").strip()
                    if not nombre_med:
                        errores.append("Fila sin medicamento.")
                        continue
                    hora_txt = str(fila.get("Hora_real", "") or "").strip()
                    justif = str(fila.get("Justificacion", "") or "").strip()
                    if accion == "No realizada" and not justif:
                        errores.append(f"{nombre_med} ({slot}): falta justificación para no realizada.")
                        continue
                    ok = registrar_administracion_dosis(
                        paciente_sel, mi_empresa, user, fecha_hoy, nombre_med, slot,
                        "Realizada" if accion == "Realizada" else "No realizada / Suspendida",
                        "" if accion == "Realizada" else justif,
                        hora_real_admin=hora_txt or None,
                    )
                    if ok:
                        registros_guardados += 1

                for e in errores[:6]:
                    st.error(e)
                if len(errores) > 6:
                    st.error(f"... y {len(errores) - 6} error(es) más.")
                if registros_guardados:
                    queue_toast(f"Se guardaron {registros_guardados} registro(s) desde la cortina.")
                    st.rerun()
                elif not errores:
                    st.info("Elegí **Realizada** o **No realizada** en al menos una fila, completá hora real y guardá.")


def render_sabana_compacta(plan_dia_df, paciente_sel, mi_empresa, user, fecha_hoy, puede_registrar_dosis):
    if plan_dia_df.empty:
        st.info("No hay administraciones planificadas para hoy.")
        return

    filas = plan_dia_df.to_dict("records")
    for idx, fila in enumerate(filas):
        hora_programada = texto_corto(fila.get("Hora programada", "--:--"), fallback="--:--", max_len=12)
        medicamento = texto_corto(fila.get("Medicamento", "Indicacion sin titulo"), fallback="Indicacion sin titulo", max_len=62)
        titulo = f"🕒 {hora_programada} | 💊 {medicamento}"
        expanded = idx < 2 and fila.get("Estado") != "Realizada"

        with st.expander(titulo, expanded=expanded):
            st.markdown('<div class="mc-rx-ficha-topbar" aria-hidden="true"></div>', unsafe_allow_html=True)
            estado_card = str(fila.get("Estado", "") or "").strip()
            estado_l = estado_card.lower()
            if estado_card == "Realizada":
                st.markdown('<span class="mc-cortina-badge mc-cortina-badge--ok">Realizada</span>', unsafe_allow_html=True)
            elif "no realizada" in estado_l or "suspendida" in estado_l:
                st.markdown('<span class="mc-cortina-badge mc-cortina-badge--no">No realizada</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="mc-cortina-badge mc-cortina-badge--pend">Pendiente</span>', unsafe_allow_html=True)

            st.caption("Compará **hora programada** con **hora real**. Podés registrar con **hora libre** si el paciente no estaba, hubo procedimiento o cambió el esquema.")
            st.markdown(f"**Vía / Frecuencia:** {texto_corto(fila.get('Via', 'S/D'), max_len=22)} | {texto_corto(fila.get('Frecuencia', 'S/D'), max_len=28)}")
            st.markdown(f"**Detalle:** {texto_corto(fila.get('Detalle / velocidad', ''), fallback='Sin detalle operativo', max_len=120)}")
            st.markdown(f"**Hora real en sistema:** {texto_corto(fila.get('Hora realizada', ''), fallback='Sin registro aún', max_len=24)}")
            observacion = str(fila.get("Observacion", "") or "").strip()
            if observacion:
                st.markdown(f"**Justificación / obs.:** {texto_corto(observacion, fallback='Sin observación', max_len=120)}")
            registrado_por = str(fila.get("Registrado por", "") or "").strip()
            if registrado_por:
                st.markdown(f"**Registró:** {texto_corto(registrado_por, fallback='Sin firma', max_len=40)}")

            if puede_registrar_dosis:
                if estado_card == "Realizada":
                    st.success("Esta administración ya figura como realizada (revisá hora real y quién registró arriba).")
                elif "no realizada" in estado_l or "suspendida" in estado_l:
                    st.info("Esta dosis figura como **no realizada** con su justificación. Para corregir o reintentar, usá **Registro manual** más abajo o coordinación según protocolo.")
                else:
                    _fk = f"rx_card_{paciente_sel}_{idx}_{str(fecha_hoy).replace('/', '-')}"
                    with st.form(_fk):
                        st.markdown("**Registrar desde la ficha**")
                        _def_hr = _default_hora_real_cortina(fila.get("Hora programada"))
                        hora_real_c = st.text_input("Hora real (HH:MM)", value=_def_hr, help="No tiene que coincidir con la hora programada.")
                        accion_c = st.radio("Acción", ["Realizada", "No realizada / Suspendida"], horizontal=True)
                        justif_c = st.text_input("Justificación (obligatoria si no realizada)", placeholder="Procedimiento, intolerancia, paciente ausente…")
                        enviar = st.form_submit_button("Guardar registro de esta medicación", use_container_width=True, type="primary")
                        if enviar:
                            nombre_med_c = str(fila.get("Medicamento", "") or "").strip()
                            slot_c = str(fila.get("Hora programada", "") or "").strip() or "A demanda"
                            if not nombre_med_c:
                                st.error("Falta el nombre de la medicación en la ficha.")
                            elif accion_c.startswith("No realizada") and not str(justif_c or "").strip():
                                st.error("Es obligatoria la justificación si marcás no realizada.")
                            elif accion_c.startswith("No realizada"):
                                if registrar_administracion_dosis(paciente_sel, mi_empresa, user, fecha_hoy, nombre_med_c, slot_c,
                                                                   "No realizada / Suspendida", justif_c, hora_real_admin=str(hora_real_c or "").strip() or None):
                                    queue_toast("Registro guardado.")
                                    st.rerun()
                            else:
                                if registrar_administracion_dosis(paciente_sel, mi_empresa, user, fecha_hoy, nombre_med_c, slot_c,
                                                                   "Realizada", "", hora_real_admin=str(hora_real_c or "").strip() or None):
                                    queue_toast(f"Administración registrada: {nombre_med_c}.")
                                    st.rerun()
