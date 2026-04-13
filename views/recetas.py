import base64
import io
import os
import re
from datetime import time as dt_time
from html import escape

import pandas as pd
import streamlit as st

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
    inferir_perfil_profesional,
    mostrar_dataframe_con_scroll,
    obtener_config_firma,
    obtener_horarios_receta,
    puede_accion,
    parse_horarios_programados,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
)


def _render_tabla_clinica(df, key=None, max_height=420, sticky_first_col=False):
    """Tabla clínica con scroll (antes faltaba en el módulo y causaba NameError en Recetas)."""
    _ = key, sticky_first_col
    mostrar_dataframe_con_scroll(df, height=max_height, border=True, hide_index=True)


def _render_dataframe_filas_tarjetas(df):
    """Vista tipo tarjeta por fila para la planilla en pantallas angostas."""
    if df is None or getattr(df, "empty", True):
        st.caption("Sin filas para mostrar.")
        return
    for idx, row in df.iterrows():
        cols_prev = list(df.columns)[:4]
        partes = []
        for c in cols_prev:
            try:
                v = str(row[c])[:52].strip()
            except Exception:
                v = ""
            if v:
                partes.append(v)
        titulo = " · ".join(partes) if partes else f"Ítem {idx}"
        with st.expander(titulo[:110], expanded=False):
            for c in df.columns:
                try:
                    val = row[c]
                except Exception:
                    val = ""
                st.markdown(f"**{escape(str(c))}:** {escape(str(val))}")


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


def _estado_icono(estado):
    estado_norm = str(estado or "").strip().lower()
    if estado_norm == "realizada":
        return "OK"
    if "no realizada" in estado_norm or "suspendida" in estado_norm:
        return "NO"
    return "PEND"


def _estado_legible(estado):
    estado_norm = str(estado or "").strip().lower()
    if estado_norm == "realizada":
        return "Realizada"
    if "no realizada" in estado_norm or "suspendida" in estado_norm:
        return "No realizada"
    return "Pendiente"


def _extraer_nombre_medicacion(texto):
    return str(texto or "").split(" | ")[0].strip()


def _resumen_plan_hidratacion(plan_hidratacion):
    if not plan_hidratacion:
        return ""
    partes = []
    for item in plan_hidratacion:
        hora = item.get("Hora sugerida", "")
        velocidad = item.get("Velocidad (ml/h)", "")
        if hora and velocidad != "":
            partes.append(f"{hora}: {velocidad} ml/h")
    return " | ".join(partes)


def _detalle_horario_infusion(registro, horario):
    plan = registro.get("plan_hidratacion", []) or []
    for item in plan:
        if item.get("Hora sugerida") == horario:
            velocidad = item.get("Velocidad (ml/h)")
            if velocidad not in ("", None):
                return f"{velocidad} ml/h"
    velocidad = registro.get("velocidad_ml_h")
    if velocidad not in ("", None):
        return f"{velocidad} ml/h"
    return registro.get("detalle_infusion", "")


def _nombre_usuario(user):
    return str(user.get("nombre", "") or "Sistema")


def _firma_trazabilidad_admin(admin_reg):
    """Texto de responsable para planillas MAR (nombre + matrícula si existe)."""
    if not admin_reg:
        return ""
    nom = str(admin_reg.get("firma", "") or "").strip()
    mp = str(admin_reg.get("matricula_profesional", "") or admin_reg.get("matricula", "") or "").strip()
    if nom and mp:
        return f"{nom} (Mat. {mp})"
    return nom or (f"Mat. {mp}" if mp else "")


def _parse_hora_hhmm(valor):
    """Devuelve 'HH:MM' normalizado, '' si vacío, o None si el texto no es una hora válida."""
    t = str(valor or "").strip()
    if not t:
        return ""
    m = re.match(r"^(\d{1,2}):(\d{1,2})$", t)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    return f"{h:02d}:{mi:02d}"


def _hora_real_para_registro(hora_real_admin):
    """
    None o vacío → hora actual. Si viene texto, debe ser HH:MM válido.
    Devuelve (str_hora, error_msg) con error_msg no vacío si falla.
    """
    if hora_real_admin is None:
        return ahora().strftime("%H:%M"), ""
    s = str(hora_real_admin).strip()
    if not s:
        return ahora().strftime("%H:%M"), ""
    p = _parse_hora_hhmm(s)
    if p is None:
        return "", "Hora real inválida. Usá formato HH:MM (ej. 08:30 o 14:05)."
    return p, ""


def _orden_horario_programado(valor):
    texto = str(valor or "").strip()
    if texto.lower() == "a demanda":
        return 9999
    partes = texto.split(":")
    if len(partes) != 2 or not all(parte.isdigit() for parte in partes):
        return 9999
    return int(partes[0]) * 60 + int(partes[1])


def _texto_corto(valor, fallback="S/D", max_len=70):
    texto = str(valor or "").strip()
    if not texto:
        return fallback
    if len(texto) > max_len:
        return f"{texto[: max_len - 3].rstrip()}..."
    return texto


def _etiqueta_receta(registro):
    nombre = _texto_corto(_extraer_nombre_medicacion(registro.get("med", "")), fallback="Indicacion sin titulo", max_len=48)
    horarios = _texto_corto(format_horarios_receta(registro), fallback="Sin horarios", max_len=34)
    estado = _texto_corto(registro.get("estado_receta", "Activa"), fallback="Activa", max_len=20)
    return f"{nombre} | {horarios} | {estado}"


def _render_plan_hidratacion_preview(plan_hidratacion):
    if not plan_hidratacion:
        return

    bloques = ["<div class='mc-rx-mini-board'>"]
    for item in plan_hidratacion[:12]:
        hora = escape(str(item.get("Hora sugerida", "--:--")))
        velocidad = escape(str(item.get("Velocidad (ml/h)", "S/D")))
        bloques.append(
            "<div class='mc-rx-mini-item'>"
            f"<span class='mc-rx-mini-hour'>{hora}</span>"
            f"<span class='mc-rx-mini-speed'>{velocidad} ml/h</span>"
            "</div>"
        )
    if len(plan_hidratacion) > 12:
        bloques.append(
            "<div class='mc-rx-mini-item mc-rx-mini-more'>"
            f"+{len(plan_hidratacion) - 12} horario(s) mas"
            "</div>"
        )
    bloques.append("</div>")
    st.markdown("".join(bloques), unsafe_allow_html=True)


def _registrar_administracion_dosis(
    paciente_sel,
    mi_empresa,
    user,
    fecha_hoy,
    nombre_med,
    horario_programado_slot,
    estado_sel,
    justificacion,
    *,
    hora_real_admin=None,
):
    """
    horario_programado_slot: hueco de la indicación (ej. 08:00) para enlazar con la planilla.
    hora_real_admin: hora en que se administró o se dejó constancia (libre); None → hora actual.
    """
    if "No realizada" in estado_sel and not justificacion.strip():
        st.error("Es obligatorio justificar por qué no se administró la dosis (documentación clínica exigible).")
        return False

    hora_str, err_h = _hora_real_para_registro(hora_real_admin)
    if err_h:
        st.error(err_h)
        return False

    slot = str(horario_programado_slot or "").strip()
    st.session_state["administracion_med_db"] = [
        a
        for a in st.session_state.get("administracion_med_db", [])
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
    st.session_state["administracion_med_db"].append(
        {
            "paciente": paciente_sel,
            "med": nombre_med,
            "fecha": fecha_hoy,
            "hora": hora_str,
            "horario_programado": horario_programado_slot,
            "estado": estado_sel,
            "motivo": justificacion.strip() if "No realizada" in estado_sel else "",
            "firma": _nombre_usuario(user),
            "matricula_profesional": mat_prof,
            "usuario_login": login_ref,
            "registro_iso": ts_evento.isoformat(timespec="seconds"),
            "registro_fecha_hora": ts_evento.strftime("%d/%m/%Y %H:%M:%S"),
            "empresa": mi_empresa,
        }
    )
    detalle_audit = (
        f"{nombre_med} | Programada: {slot} | Hora administración/registro: {hora_str} | Estado: {estado_sel}"
    )
    if "No realizada" in estado_sel and justificacion.strip():
        detalle_audit += f" | Justificación: {justificacion.strip()[:200]}"
    registrar_auditoria_legal(
        "Medicacion",
        paciente_sel,
        "Registro MAR / administración de medicación",
        user.get("nombre", ""),
        user.get("matricula", ""),
        detalle_audit,
        referencia=f"MAR|{fecha_hoy}|{slot}|{nombre_med[:48]}",
        extra={
            "horario_programado": slot,
            "hora_clinica": hora_str,
            "estado_administracion": estado_sel,
            "modulo_ui": "Recetas",
        },
        empresa=mi_empresa,
        usuario=user if isinstance(user, dict) else None,
        modulo="Recetas / MAR",
        criticidad="alta",
    )
    guardar_datos()
    return True


def _guardar_administracion_medicacion(
    paciente_sel, mi_empresa, user, nombre_med, fecha_hoy, horario_sel, estado_sel, *, hora_real_admin=None
):
    """Registro rápido desde grilla 24 h o atajos (sin justificación obligatoria para Realizada)."""
    return _registrar_administracion_dosis(
        paciente_sel,
        mi_empresa,
        user,
        fecha_hoy,
        nombre_med,
        horario_sel,
        estado_sel,
        "",
        hora_real_admin=hora_real_admin,
    )


def _construir_matriz_registro_24h(plan_dia_df):
    """
    Una fila por dosis planificada del día; columnas 00:00–23:00 y A demanda.
    True = ya administrada, False = pendiente (tildable), pd.NA = no aplica.
    """
    horas_mar = [f"{h:02d}:00" for h in range(24)]
    if plan_dia_df.empty:
        return [], horas_mar, {}

    matriz_registro_rows = []
    matriz_registro_map = {}

    for mat_idx, (_, r) in enumerate(plan_dia_df.iterrows()):
        med = str(r.get("Medicamento", "") or "").strip()
        via = str(r.get("Via", "") or "").strip() or "S/D"
        freq = str(r.get("Frecuencia", "") or "").strip() or "S/D"
        detalle = str(r.get("Detalle / velocidad", "") or "").strip()
        hp = str(r.get("Hora programada", "") or "").strip()
        estado_ok = str(r.get("Estado", "") or "").strip() == "Realizada"

        row_dict = {
            "Indicacion": med,
            "Via": via,
            "Frecuencia": freq,
            "Detalle": detalle,
        }
        for h in horas_mar:
            row_dict[h] = pd.NA
        row_dict["A demanda"] = pd.NA

        col = None
        if hp.lower() == "a demanda":
            col = "A demanda"
            row_dict[col] = estado_ok
        else:
            partes = hp.split(":")
            if len(partes) >= 2 and str(partes[0]).strip().isdigit():
                col = f"{int(str(partes[0]).strip()) % 24:02d}:00"
                if col in row_dict:
                    row_dict[col] = estado_ok

        if col:
            matriz_registro_map[(mat_idx, col)] = {
                "medicamento": med,
                "horario_programado": hp if hp.lower() != "a demanda" else "A demanda",
            }

        matriz_registro_rows.append(row_dict)

    return matriz_registro_rows, horas_mar, matriz_registro_map


def _tabla_guardia_operativa(plan_dia_df):
    columnas_base = ["Hora", "Medicacion", "Indicacion", "Estado", "Registro"]
    if plan_dia_df.empty:
        return pd.DataFrame(columns=columnas_base)

    tabla = plan_dia_df.copy()
    tabla["Indicacion"] = tabla.apply(
        lambda fila: " | ".join(
            parte
            for parte in [
                _texto_corto(fila.get("Via", ""), fallback="", max_len=18),
                _texto_corto(fila.get("Frecuencia", ""), fallback="", max_len=24),
            ]
            if parte
        )
        or "S/D",
        axis=1,
    )
    tabla["Registro"] = tabla.apply(
        lambda fila: _texto_corto(fila.get("Hora realizada", ""), fallback="", max_len=12)
        if str(fila.get("Hora realizada", "")).strip()
        else _texto_corto(fila.get("Registrado por", ""), fallback="Sin registro", max_len=26),
        axis=1,
    )
    tabla["Observacion corta"] = tabla["Observacion"].apply(lambda valor: _texto_corto(valor, fallback="", max_len=32))

    columnas = ["Hora programada", "Medicamento", "Indicacion", "Estado", "Registro"]
    if tabla["Observacion corta"].astype(str).str.strip().any():
        columnas.append("Observacion corta")

    return tabla[columnas].rename(
        columns={
            "Hora programada": "Hora",
            "Medicamento": "Medicacion",
            "Observacion corta": "Obs.",
        }
    )


def _tabla_guardia_detallada(plan_dia_df):
    columnas_base = ["Hora", "Hora real", "Medicacion", "Detalle", "Indicacion", "Estado", "Observacion", "Registrado por"]
    if plan_dia_df.empty:
        return pd.DataFrame(columns=columnas_base)

    tabla = plan_dia_df.copy()
    tabla["Indicacion"] = tabla.apply(
        lambda fila: " | ".join(
            parte
            for parte in [
                _texto_corto(fila.get("Via", ""), fallback="", max_len=18),
                _texto_corto(fila.get("Frecuencia", ""), fallback="", max_len=24),
            ]
            if parte
        )
        or "S/D",
        axis=1,
    )

    return tabla[
        [
            "Hora programada",
            "Hora realizada",
            "Medicamento",
            "Detalle / velocidad",
            "Indicacion",
            "Estado",
            "Observacion",
            "Registrado por",
        ]
    ].rename(
        columns={
            "Hora programada": "Hora",
            "Hora realizada": "Hora real",
            "Medicamento": "Medicacion",
            "Detalle / velocidad": "Detalle",
        }
    )


def _html_cortina_resumen_visual(plan_dia_df):
    """Vista completa del turno: colores verde / rojo / ámbar y trazabilidad."""
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


def _render_cortina_tildado_rapido(
    pendientes_base: pd.DataFrame,
    paciente_sel: str,
    mi_empresa: str,
    user: dict,
    fecha_hoy: str,
) -> None:
    """
    Cortina compacta: pocas columnas + tilde + hora real. Evita la tabla ancha del editor completo.
    """
    if pendientes_base.empty:
        return
    st.markdown(
        '<p class="mc-cortina-rapida-titulo">Cortina rápida — tilde solo lo que diste ahora</p>',
        unsafe_allow_html=True,
    )
    st.caption("Marcá **Dada**, ajustá **Hora real** si hace falta, y guardá. Para **no realizada** usá el registro avanzado abajo.")

    rapida = pendientes_base[
        ["Hora programada", "Medicamento", "Via", "Frecuencia"]
    ].copy()
    rapida["Dada"] = False
    rapida["Hora_real"] = rapida["Hora programada"].map(_default_hora_real_cortina)

    ed_rap = st.data_editor(
        rapida,
        hide_index=True,
        width="stretch",
        disabled=["Hora programada", "Medicamento", "Via", "Frecuencia"],
        column_config={
            "Hora programada": st.column_config.TextColumn("Prog.", width="small"),
            "Medicamento": st.column_config.TextColumn("Medicación", width="medium"),
            "Via": st.column_config.TextColumn("Vía", width="small"),
            "Frecuencia": st.column_config.TextColumn("Frec.", width="small"),
            "Dada": st.column_config.CheckboxColumn(
                "Dada",
                help="Solo si administraste esta dosis en esta franja.",
                default=False,
            ),
            "Hora_real": st.column_config.TextColumn("Hora real", max_chars=8, width="small"),
        },
        key=f"cortina_rapida_{paciente_sel}_{fecha_hoy}",
    )

    if st.button(
        "Guardar tildes rápidos",
        width="stretch",
        type="primary",
        key=f"guardar_cortina_rapida_{paciente_sel}_{fecha_hoy}",
    ):
        n = 0
        for _, fila in ed_rap.iterrows():
            if not bool(fila.get("Dada")):
                continue
            med = str(fila.get("Medicamento", "") or "").strip()
            slot = str(fila.get("Hora programada", "") or "").strip()
            hr = str(fila.get("Hora_real", "") or "").strip()
            if not med:
                continue
            if _registrar_administracion_dosis(
                paciente_sel,
                mi_empresa,
                user,
                fecha_hoy,
                med,
                slot,
                "Realizada",
                "",
                hora_real_admin=hr or None,
            ):
                n += 1
        if n:
            st.success(f"Listo: {n} administración(es) registrada(s).")
            st.rerun()
        else:
            st.info("Tildá **Dada** en al menos una fila o usá el registro avanzado.")


def _default_hora_real_cortina(hp_raw):
    hp = str(hp_raw or "").strip()
    if hp.lower() == "a demanda" or not hp:
        return ahora().strftime("%H:%M")
    norm = _parse_hora_hhmm(hp)
    return norm if norm else hp


def _cortina_mar_key_slug(paciente_sel: str, fecha_hoy: str) -> str:
    p = re.sub(r"[^\w\-]", "_", str(paciente_sel))[:44]
    f = str(fecha_hoy).replace("/", "_").replace(" ", "_")
    return f"{p}_{f}"


def _render_marco_clinico_cortina():
    """Referencia internacional (seguridad del medicamento) y marco legal genérico para la jurisdicción local."""
    with st.expander(
        "Seguridad del medicamento, trazabilidad y marco legal (referencia internacional)",
        expanded=False,
    ):
        st.markdown(
            """
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
            """
        )


def _render_cortina_mar_hospitalaria(
    plan_dia_df: pd.DataFrame,
    paciente_sel: str,
    mi_empresa: str,
    user: dict,
    fecha_hoy: str,
) -> None:
    """
    Planilla tipo MAR: fila con «Validado», bloque clínico y acción (realizada / no realizada).
    Muestra todo el día para contexto; solo las pendientes son editables.
    """
    if plan_dia_df.empty:
        return
    suf = _cortina_mar_key_slug(paciente_sel, fecha_hoy)
    st.markdown(
        '<p class="mc-mar-encabezado">Planilla MAR — administración del turno</p>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Registro tipo **hoja de administración de medicación (MAR)**: **Realizada** con hora clínica libre; "
        "**No realizada** con **motivo obligatorio** (estándar de trazabilidad). Filas completadas: estado a la derecha."
    )
    plan_ord = plan_dia_df.reset_index(drop=True)
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
        hp = escape(str(fila.get("Hora programada", "") or "—"))
        hr_reg = str(fila.get("Hora realizada", "") or "").strip()
        hr_e = escape(hr_reg if hr_reg else "—")
        firma = escape(str(fila.get("Registrado por", "") or "").strip())
        obs = str(fila.get("Observacion", "") or "").strip()
        obs_e = escape(obs) if obs else ""

        if es_pend:
            blk = "mc-mar-block mc-mar-block--pend"
        elif es_ok:
            blk = "mc-mar-block mc-mar-block--ok"
        elif es_no:
            blk = "mc-mar-block mc-mar-block--no"
        else:
            blk = "mc-mar-block"

        ritmo_inner = f"Horario programado <b>{hp}</b> · Hora administración/registro <b>{hr_e}</b>"
        if es_ok and firma:
            ritmo_inner += f' · <span class="mc-mar-firma">Profesional: {firma}</span>'

        extra_obs = (
            f'<div class="mc-mar-chip-note"><b>Justif.</b> {obs_e}</div>' if (es_no and obs_e) else ""
        )

        with st.container(border=True):
            c0, c1, c2 = st.columns([0.82, 3.85, 2.55])
            with c0:
                st.markdown(
                    '<div class="mc-mar-validado" title="Indicación médica vigente en el sistema (prescripción activa)">'
                    "Indicación<br/>activa</div>",
                    unsafe_allow_html=True,
                )
            with c1:
                st.markdown(
                    f'<div class="{blk}">'
                    f'<div class="mc-mar-title">{med.upper()}</div>'
                    f'<div class="mc-mar-sub">{via} · {freq}</div>'
                    f'<div class="mc-mar-detail">{det}</div>'
                    f'<div class="mc-mar-ritmo">{ritmo_inner}</div>'
                    f"{extra_obs}</div>",
                    unsafe_allow_html=True,
                )
            with c2:
                if es_pend:
                    k_hr = f"mar_hr_{suf}_{i}"
                    k_just = f"mar_just_{suf}_{i}"
                    def_h = _default_hora_real_cortina(fila.get("Hora programada"))
                    st.text_input(
                        "Hora de administración o constancia (HH:MM)",
                        value=def_h,
                        max_chars=8,
                        key=k_hr,
                        help="Hora clínica a dejar en legajo; puede diferir de la programada (demora, procedimiento, etc.).",
                    )
                    st.text_input(
                        "Motivo clínico (obligatorio si no se administra)",
                        value="",
                        max_chars=400,
                        key=k_just,
                        placeholder="Ej. Paciente ausente, rechazo, ayuno, orden médica de suspensión…",
                    )
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button(
                            "Administración realizada",
                            key=f"mar_ok_{suf}_{i}",
                            type="primary",
                            width="stretch",
                            help="Registra administración conforme a la indicación (queda firmado y auditado).",
                        ):
                            hr_val = str(st.session_state.get(k_hr, def_h) or "").strip() or def_h
                            if _registrar_administracion_dosis(
                                paciente_sel,
                                mi_empresa,
                                user,
                                fecha_hoy,
                                med_raw,
                                str(fila.get("Hora programada", "") or "").strip(),
                                "Realizada",
                                "",
                                hora_real_admin=hr_val,
                            ):
                                st.rerun()
                    with b2:
                        if st.button(
                            "No administrada / suspendida",
                            key=f"mar_no_{suf}_{i}",
                            width="stretch",
                            help="Requiere motivo clínico documentado (trazabilidad legal).",
                        ):
                            just = str(st.session_state.get(k_just, "") or "").strip()
                            hr_val = str(st.session_state.get(k_hr, def_h) or "").strip() or def_h
                            if not just:
                                st.error(
                                    "Documentá el motivo clínico antes de registrar una omisión (requisito de historia clínica)."
                                )
                            elif _registrar_administracion_dosis(
                                paciente_sel,
                                mi_empresa,
                                user,
                                fecha_hoy,
                                med_raw,
                                str(fila.get("Hora programada", "") or "").strip(),
                                "No realizada / Suspendida",
                                just,
                                hora_real_admin=hr_val,
                            ):
                                st.rerun()
                elif es_ok:
                    st.markdown(
                        '<span class="mc-mar-chip mc-mar-chip--ok">Administrada</span>',
                        unsafe_allow_html=True,
                    )
                elif es_no:
                    st.markdown(
                        '<span class="mc-mar-chip mc-mar-chip--no">No administrada</span>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption(estado or "—")


def _render_bloque_cortina_medicacion(
    plan_dia_df,
    columnas_tabla,
    paciente_sel,
    mi_empresa,
    user,
    fecha_hoy,
    puede_registrar_dosis,
):
    """
    Cortina: vista completa del turno (colores) + registro con hora libre y no realizada con justificación.
    """
    if plan_dia_df.empty:
        return

    def _fila_pendiente_cortina(estado) -> bool:
        return str(estado or "").strip().lower() == "pendiente"

    pendientes_base = plan_dia_df[plan_dia_df["Estado"].map(_fila_pendiente_cortina)].copy().reset_index(drop=True)
    n_pend = len(pendientes_base)
    n_ok = int((plan_dia_df["Estado"].astype(str).str.strip() == "Realizada").sum())

    if n_pend:
        st.info(
            f"**Cortina de medicación:** abrí el panel para ver **toda** la planilla del día (verde/rojo), "
            f"**{n_ok}** realizada(s) y registrar **{n_pend}** pendiente(s) con **hora real libre**.",
            icon="📋",
        )
    else:
        st.success(
            "No quedan filas **pendientes** en la planilla de hoy (puede haber realizadas o no realizadas). "
            "Abrí la cortina para ver la trazabilidad completa del turno.",
            icon="✅",
        )

    with st.expander(
        "**Cortina de medicación** · Vista completa, hora libre y estados (tablet / PC)",
        expanded=False,
    ):
        st.markdown(_html_cortina_resumen_visual(plan_dia_df), unsafe_allow_html=True)

        st.caption(
            "**Verde** = administrada · **Rojo** = no administrada (con justificación documentada) · **Ámbar** = pendiente. "
            "La **hora de registro** puede diferir de la programada (paciente ausente, procedimiento, tolerancia, etc.)."
        )
        _render_marco_clinico_cortina()

        if not puede_registrar_dosis:
            st.warning("Solo lectura: tu rol no puede registrar administración desde acá.")
            return

        if pendientes_base.empty:
            st.caption("No hay filas pendientes para registrar en esta vista.")
            return

        _render_cortina_mar_hospitalaria(
            plan_dia_df, paciente_sel, mi_empresa, user, fecha_hoy
        )

        with st.expander("Vista tabla rápida (alternativa)", expanded=False):
            st.caption("Misma lógica que la planilla MAR: tilde **Dada** y **Guardar** si preferís grilla compacta.")
            _render_cortina_tildado_rapido(
                pendientes_base, paciente_sel, mi_empresa, user, fecha_hoy
            )

        with st.expander("Registro avanzado — no realizada, justificación y todas las columnas", expanded=False):
            st.caption(
                "Usalo si necesitás marcar **No realizada** con motivo, o revisar observaciones y registro previo en la misma grilla."
            )
            pendientes_df = pendientes_base.copy()
            pendientes_df["Accion"] = "(sin cambio)"
            pendientes_df["Hora_real"] = pendientes_df["Hora programada"].map(_default_hora_real_cortina)
            pendientes_df["Justificacion"] = ""

            _cols_ref = [c for c in columnas_tabla if c in pendientes_df.columns]
            editor_columnas = _cols_ref + ["Accion", "Hora_real", "Justificacion"]
            disabled_cols = [c for c in editor_columnas if c not in ("Accion", "Hora_real", "Justificacion")]

            editor_df = st.data_editor(
                pendientes_df[editor_columnas],
                hide_index=True,
                width="stretch",
                disabled=disabled_cols,
                column_config={
                    "Accion": st.column_config.SelectboxColumn(
                        "Acción",
                        help="Realizada: se dio la dosis (hora real editable). No realizada: obligatorio justificar.",
                        options=["(sin cambio)", "Realizada", "No realizada"],
                        required=True,
                    ),
                    "Hora_real": st.column_config.TextColumn(
                        "Hora real (HH:MM)",
                        help="Hora en que administraste o dejaste constancia. No tiene que coincidir con la programada.",
                        max_chars=8,
                    ),
                    "Justificacion": st.column_config.TextColumn(
                        "Justificación (si no realizada)",
                        max_chars=400,
                    ),
                },
                key=f"cortina_tabla_editor_{paciente_sel}_{fecha_hoy}",
            )

            if st.button(
                "Guardar registro avanzado (cortina)",
                width="stretch",
                key=f"guardar_tildes_cortina_{paciente_sel}_{fecha_hoy}",
            ):
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

                    if accion == "Realizada":
                        ok = _registrar_administracion_dosis(
                            paciente_sel,
                            mi_empresa,
                            user,
                            fecha_hoy,
                            nombre_med,
                            slot,
                            "Realizada",
                            "",
                            hora_real_admin=hora_txt or None,
                        )
                    else:
                        ok = _registrar_administracion_dosis(
                            paciente_sel,
                            mi_empresa,
                            user,
                            fecha_hoy,
                            nombre_med,
                            slot,
                            "No realizada / Suspendida",
                            justif,
                            hora_real_admin=hora_txt or None,
                        )
                    if ok:
                        registros_guardados += 1

                for e in errores[:6]:
                    st.error(e)
                if len(errores) > 6:
                    st.error(f"... y {len(errores) - 6} error(es) más.")

                if registros_guardados:
                    st.success(f"Se guardaron {registros_guardados} registro(s) desde la cortina.")
                    st.rerun()
                elif not errores:
                    st.info("Elegí **Realizada** o **No realizada** en al menos una fila, completá hora real y guardá.")


def _render_sabana_compacta(plan_dia_df, paciente_sel, mi_empresa, user, fecha_hoy, puede_registrar_dosis):
    if plan_dia_df.empty:
        st.info("No hay administraciones planificadas para hoy.")
        return

    filas = plan_dia_df.to_dict("records")
    for idx, fila in enumerate(filas):
        hora_programada = _texto_corto(fila.get("Hora programada", "--:--"), fallback="--:--", max_len=12)
        medicamento = _texto_corto(fila.get("Medicamento", "Indicacion sin titulo"), fallback="Indicacion sin titulo", max_len=62)
        titulo = f"🕒 {hora_programada} | 💊 {medicamento}"
        expanded = idx < 2 and fila.get("Estado") != "Realizada"

        with st.expander(titulo, expanded=expanded):
            st.markdown('<div class="mc-rx-ficha-topbar" aria-hidden="true"></div>', unsafe_allow_html=True)
            estado_card = str(fila.get("Estado", "") or "").strip()
            estado_l = estado_card.lower()
            if estado_card == "Realizada":
                st.markdown(
                    '<span class="mc-cortina-badge mc-cortina-badge--ok">Realizada</span>',
                    unsafe_allow_html=True,
                )
            elif "no realizada" in estado_l or "suspendida" in estado_l:
                st.markdown(
                    '<span class="mc-cortina-badge mc-cortina-badge--no">No realizada</span>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<span class="mc-cortina-badge mc-cortina-badge--pend">Pendiente</span>',
                    unsafe_allow_html=True,
                )

            st.caption(
                "Compará **hora programada** con **hora real**. Podés registrar con **hora libre** si el paciente no estaba, hubo procedimiento o cambió el esquema."
            )
            st.markdown(
                f"**Vía / Frecuencia:** {_texto_corto(fila.get('Via', 'S/D'), max_len=22)} | {_texto_corto(fila.get('Frecuencia', 'S/D'), max_len=28)}"
            )
            st.markdown(
                f"**Detalle:** {_texto_corto(fila.get('Detalle / velocidad', ''), fallback='Sin detalle operativo', max_len=120)}"
            )
            st.markdown(
                f"**Hora real en sistema:** {_texto_corto(fila.get('Hora realizada', ''), fallback='Sin registro aún', max_len=24)}"
            )
            observacion = str(fila.get("Observacion", "") or "").strip()
            if observacion:
                st.markdown(f"**Justificación / obs.:** {_texto_corto(observacion, fallback='Sin observación', max_len=120)}")
            registrado_por = str(fila.get("Registrado por", "") or "").strip()
            if registrado_por:
                st.markdown(f"**Registró:** {_texto_corto(registrado_por, fallback='Sin firma', max_len=40)}")

            if puede_registrar_dosis:
                if estado_card == "Realizada":
                    st.success("Esta administración ya figura como realizada (revisá hora real y quién registró arriba).")
                elif "no realizada" in estado_l or "suspendida" in estado_l:
                    st.info(
                        "Esta dosis figura como **no realizada** con su justificación. "
                        "Para corregir o reintentar, usá **Registro manual** más abajo o coordinación según protocolo."
                    )
                else:
                    _fk = f"rx_card_{paciente_sel}_{idx}_{str(fecha_hoy).replace('/', '-')}"
                    with st.form(_fk):
                        st.markdown("**Registrar desde la ficha**")
                        _def_hr = _default_hora_real_cortina(fila.get("Hora programada"))
                        hora_real_c = st.text_input(
                            "Hora real (HH:MM)",
                            value=_def_hr,
                            help="No tiene que coincidir con la hora programada.",
                        )
                        accion_c = st.radio(
                            "Acción",
                            ["Realizada", "No realizada / Suspendida"],
                            horizontal=True,
                        )
                        justif_c = st.text_input(
                            "Justificación (obligatoria si no realizada)",
                            placeholder="Procedimiento, intolerancia, paciente ausente…",
                        )
                        enviar = st.form_submit_button(
                            "Guardar registro de esta medicación", width="stretch", type="primary"
                        )
                        if enviar:
                            nombre_med_c = str(fila.get("Medicamento", "") or "").strip()
                            slot_c = str(fila.get("Hora programada", "") or "").strip() or "A demanda"
                            if not nombre_med_c:
                                st.error("Falta el nombre de la medicación en la ficha.")
                            elif accion_c.startswith("No realizada") and not str(justif_c or "").strip():
                                st.error("Es obligatoria la justificación si marcás no realizada.")
                            elif accion_c.startswith("No realizada"):
                                if _registrar_administracion_dosis(
                                    paciente_sel,
                                    mi_empresa,
                                    user,
                                    fecha_hoy,
                                    nombre_med_c,
                                    slot_c,
                                    "No realizada / Suspendida",
                                    justif_c,
                                    hora_real_admin=str(hora_real_c or "").strip() or None,
                                ):
                                    st.success("Registro guardado.")
                                    st.rerun()
                            else:
                                if _registrar_administracion_dosis(
                                    paciente_sel,
                                    mi_empresa,
                                    user,
                                    fecha_hoy,
                                    nombre_med_c,
                                    slot_c,
                                    "Realizada",
                                    "",
                                    hora_real_admin=str(hora_real_c or "").strip() or None,
                                ):
                                    st.success(f"Administración registrada: {nombre_med_c}.")
                                    st.rerun()


def _construir_texto_indicacion(
    tipo_indicacion,
    med_final="",
    via="",
    frecuencia="",
    dias=None,
    solucion="",
    volumen_ml=None,
    velocidad_ml_h=None,
    alternar_con="",
    detalle_infusion="",
    plan_hidratacion=None,
):
    if tipo_indicacion == "Infusion / hidratacion":
        partes = []
        titulo = solucion.strip() or "Infusion endovenosa"
        if volumen_ml:
            titulo = f"{titulo} {int(volumen_ml)} ml"
        partes.append(titulo)
        if via:
            partes.append(f"Via: {via}")
        if velocidad_ml_h not in ("", None):
            partes.append(f"Velocidad: {velocidad_ml_h} ml/h")
        if alternar_con:
            partes.append(f"Alternar con: {alternar_con}")
        if dias:
            partes.append(f"Durante {dias} dias")
        if plan_hidratacion:
            resumen = _resumen_plan_hidratacion(plan_hidratacion)
            if resumen:
                partes.append(f"Plan: {resumen}")
        if detalle_infusion:
            partes.append(f"Indicacion: {detalle_infusion.strip()}")
        return " | ".join([p for p in partes if str(p).strip()])

    texto_base = med_final.strip().title()
    partes = [texto_base]
    if via:
        partes.append(f"Via: {via}")
    if frecuencia:
        partes.append(frecuencia)
    if dias:
        partes.append(f"Durante {dias} dias")
    return " | ".join([p for p in partes if str(p).strip()])


def render_recetas(paciente_sel, mi_empresa, user, rol=None):
    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral.")
        return

    rol = rol or user.get("rol", "")
    nombre_usuario = _nombre_usuario(user)
    perfil_usuario = inferir_perfil_profesional(user)
    perfil_usuario_norm = str(perfil_usuario or "").strip().lower()
    puede_prescribir = puede_accion(rol, "recetas_prescribir")
    puede_cargar_papel = puede_accion(rol, "recetas_cargar_papel")
    puede_registrar_dosis = puede_accion(rol, "recetas_registrar_dosis")
    puede_cambiar_estado = puede_accion(rol, "recetas_cambiar_estado")

    st.markdown(
        """
        <div class="mc-rx-hero-premium">
            <p class="mc-rx-hero-kicker">Medicación con estándar clínico</p>
            <h2 class="mc-rx-hero-title">Prescripción y administración seguras</h2>
            <p class="mc-rx-hero-lead">
                Cada decisión sobre un medicamento puede marcar el cuidado del paciente. Esta vista prioriza
                <strong style="color:#e2e8f0;">orden, claridad y registro completo</strong> para que el equipo trabaje
                con la misma información y con respaldo documental.
            </p>
            <div class="mc-rx-trust-bar">
                <span class="mc-rx-trust-ico" aria-hidden="true">⚖️</span>
                <p class="mc-rx-trust-text">
                    <strong>Trazabilidad legal:</strong> prescripciones, administraciones, horarios reales, usuario y
                    justificaciones quedan auditadas. Verificá siempre paciente, vía y dosis antes de confirmar.
                </p>
            </div>
            <div class="mc-rx-chip-row-premium">
                <span class="mc-rx-chip-premium mc-rx-chip--legal">Auditoría en cada guardado</span>
                <span class="mc-rx-chip-premium">Catálogo y firma profesional</span>
                <span class="mc-rx-chip-premium mc-rx-chip--safe">Sábana y cortina del turno</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        f"Profesional en sesión: **{nombre_usuario}** · Los registros asocian usuario, fecha/hora y contexto clínico para revisión posterior."
    )

    if perfil_usuario_norm in {"operativo", "enfermeria"}:
        st.markdown(
            """
            <div class="mc-rx-callout-care">
                <span class="mc-rx-callout-ico" aria-hidden="true">🩺</span>
                <p>
                    <strong>Enfermería y equipo asistencial:</strong> tenés la planilla del día, la cortina para registrar
                    con hora real libre, las fichas compactas y el registro manual. Ante duda, detené el proceso y
                    consultá: la medicación mal administrada es un riesgo evitable.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    try:
        vademecum_base = cargar_json_asset("vademecum.json")
    except Exception:
        vademecum_base = ["Medicamento 1", "Medicamento 2"]

    st.markdown(
        """
        <div class="mc-rx-pillars">
            <div class="mc-rx-pillar">
                <span class="mc-rx-pillar-num">1</span>
                <h4>Precisión</h4>
                <p>Catálogo guiado y textos estandarizados reducen ambigüedad en fármaco, vía y pauta.</p>
            </div>
            <div class="mc-rx-pillar">
                <span class="mc-rx-pillar-num">2</span>
                <h4>Constancia legal</h4>
                <p>Recetas y administraciones conservan profesional, matrícula, sellos de tiempo y adjuntos cuando corresponde.</p>
            </div>
            <div class="mc-rx-pillar">
                <span class="mc-rx-pillar-num">3</span>
                <h4>Control del turno</h4>
                <p>Métricas, cortina y fichas muestran pendientes, realizadas y no realizadas con motivo explícito.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if puede_prescribir:
        st.markdown(
            """
            <div class="mc-rx-section-head mc-rx-section-head--tight">
                <h3 class="mc-rx-section-title">Nueva prescripción médica</h3>
                <p class="mc-rx-section-sub">Completá la indicación con el detalle suficiente para que enfermería ejecute sin interpretaciones dudosas.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
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

                c4, c5, c6 = st.columns([1, 1, 1])
                velocidad_ml_h = c4.number_input(
                    "Velocidad (ml/h)",
                    min_value=0.0,
                    step=1.0,
                    value=21.0,
                    key="velocidad_receta",
                )
                duracion_horas = c5.number_input(
                    "Duracion estimada (horas)",
                    min_value=0.0,
                    step=0.5,
                    value=0.0,
                    key="duracion_horas_receta",
                )
                alternar_con = c6.selectbox(
                    "Alternar con",
                    ["", "Fisiologico 0.9%", "Ringer lactato", "Dextrosa 5%", "Otra"],
                    key="alternar_con_receta",
                )

                hora_inicio = st.time_input(
                    "Hora inicial del plan de infusion",
                    value=dt_time(8, 0),
                    key="hora_inicio_infusion_receta",
                )
                detalle_infusion = st.text_area(
                    "Indicacion medica de infusion / hidratacion",
                    placeholder=(
                        "Ej: pasar Dextrosa 5% 500 ml a 21 ml/h, alternar con Fisiologico 0.9% por bolsa. "
                        "Aumentar segun tolerancia y control clinico."
                    ),
                    key="detalle_infusion_receta",
                )

                velocidad_sugerida = calcular_velocidad_ml_h(volumen_ml, duracion_horas)
                if velocidad_sugerida is not None:
                    st.caption(
                        f"Referencia de calculo: {int(volumen_ml)} ml / {duracion_horas:g} h = {velocidad_sugerida:g} ml/h."
                    )

                usar_plan_escalonado = st.checkbox(
                    "Plan escalonado de hidratacion / infusion",
                    value=False,
                    key="usar_plan_escalonado_receta",
                )
                if usar_plan_escalonado:
                    c7, c8, c9, c10 = st.columns(4)
                    inicio_ml_h = c7.number_input("Inicio (ml/h)", min_value=1, step=1, value=21, key="inicio_ml_h_receta")
                    maximo_ml_h = c8.number_input("Maximo (ml/h)", min_value=1, step=1, value=54, key="maximo_ml_h_receta")
                    incremento_ml_h = c9.number_input("Incremento (ml/h)", min_value=1, step=1, value=7, key="incremento_ml_h_receta")
                    intervalo_horas = c10.number_input(
                        "Cada cuantas horas",
                        min_value=1,
                        step=1,
                        value=1,
                        key="intervalo_escalonado_receta",
                    )
                    plan_hidratacion = generar_plan_escalonado_ml_h(
                        inicio_ml_h,
                        maximo_ml_h,
                        incremento_ml_h,
                        hora_inicio.strftime("%H:%M"),
                        intervalo_horas,
                    )
                    if plan_hidratacion:
                        st.caption("Vista previa del plan de infusion / hidratacion")
                        _render_plan_hidratacion_preview(plan_hidratacion)
                        horarios_sugeridos = [item["Hora sugerida"] for item in plan_hidratacion]
                    else:
                        horarios_sugeridos = [hora_inicio.strftime("%H:%M")]
                else:
                    horarios_sugeridos = [hora_inicio.strftime("%H:%M")]
                    st.caption(
                        "Referencia general de bomba: ml/h = volumen total (ml) / tiempo (h). "
                        "Verificar siempre con protocolo institucional y criterio medico."
                    )
                st.caption(f"Horarios visibles en la sabana diaria: {' | '.join(horarios_sugeridos)}")

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

            if st.button("Guardar prescripcion medica", width="stretch", type="primary"):
                med_final = med_manual.strip().title() if med_manual.strip() else med_vademecum
                if tipo_indicacion == "Medicacion" and (not med_final or med_final == "-- Seleccionar del vademecum --"):
                    st.error("Debe seleccionar o escribir un medicamento.")
                elif tipo_indicacion == "Infusion / hidratacion" and not solucion.strip():
                    st.error("Debe indicar la solucion principal.")
                elif tipo_indicacion == "Infusion / hidratacion" and not detalle_infusion.strip():
                    st.error("Debe explicar como pasar la infusion o hidratacion.")
                elif tipo_indicacion == "Infusion / hidratacion" and (velocidad_ml_h in (None, "", 0) and not plan_hidratacion):
                    st.error("Debe indicar una velocidad en ml/h o cargar un plan escalonado.")
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
                        guardar_datos()
                        st.success(f"Prescripcion de {med_final} guardada con firma medica.")
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
                c_inf_p1, c_inf_p2, c_inf_p3 = st.columns(3)
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
                velocidad_papel = c_inf_p3.number_input(
                    "Velocidad (ml/h)",
                    min_value=0.0,
                    step=1.0,
                    value=21.0,
                    key="velocidad_papel_receta",
                )
                alternar_papel = st.selectbox(
                    "Alternar con",
                    ["", "Fisiologico 0.9%", "Ringer lactato", "Dextrosa 5%", "Otra"],
                    key="alternar_papel_receta",
                )
                detalle_papel = st.text_area(
                    "Explicacion medica de la infusion / hidratacion",
                    key="detalle_papel_infusion_receta",
                    placeholder="Ej: pasar Dextrosa 5% 500 ml a 21 ml/h, alternar con Ringer lactato por bolsa y aumentar segun tolerancia.",
                )
                usar_plan_papel = st.checkbox(
                    "Plan escalonado en la orden",
                    value=False,
                    key="usar_plan_papel_receta",
                )
                if usar_plan_papel:
                    c_inf_p4, c_inf_p5, c_inf_p6, c_inf_p7 = st.columns(4)
                    inicio_papel = c_inf_p4.number_input("Inicio (ml/h)", min_value=1, step=1, value=21, key="inicio_papel_receta")
                    maximo_papel = c_inf_p5.number_input("Maximo (ml/h)", min_value=1, step=1, value=54, key="maximo_papel_receta")
                    incremento_papel = c_inf_p6.number_input("Incremento (ml/h)", min_value=1, step=1, value=7, key="incremento_papel_receta")
                    intervalo_papel = c_inf_p7.number_input("Cada cuantas horas", min_value=1, step=1, value=1, key="intervalo_papel_receta")
                    plan_papel = generar_plan_escalonado_ml_h(
                        inicio_papel,
                        maximo_papel,
                        incremento_papel,
                        hora_papel.strftime("%H:%M"),
                        intervalo_papel,
                    )
                    if plan_papel:
                        _render_plan_hidratacion_preview(plan_papel)
                        horarios_papel = [item["Hora sugerida"] for item in plan_papel]
                if not horarios_papel:
                    horarios_papel = [hora_papel.strftime("%H:%M")]
                st.caption(f"Horarios visibles en la sabana diaria: {' | '.join(horarios_papel)}")
            adjunto_papel = st.file_uploader(
                "Subir orden medica en papel o PDF",
                type=["pdf", "png", "jpg", "jpeg"],
                key="adjunto_papel_receta",
            )
            if st.button("Guardar indicacion en papel", width="stretch", key="guardar_indicacion_papel"):
                if not medico_papel.strip() or not matricula_papel.strip():
                    st.error("Debe completar medico y matricula para dejar respaldo legal.")
                elif not detalle_papel.strip():
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
        st.markdown(
            """
            <div class="mc-rx-section-head">
                <h3 class="mc-rx-section-title">Administración del turno</h3>
                <p class="mc-rx-section-sub">
                    Planilla del día con métricas en vivo. Usá la cortina o las fichas para dejar constancia clara:
                    cada guardado queda firmado y auditado.
                </p>
            </div>
            <ul class="mc-rx-flow" aria-label="Flujo sugerido">
                <li><span class="mc-rx-flow-n">1</span> Revisar métricas</li>
                <li><span class="mc-rx-flow-n">2</span> Abrir cortina</li>
                <li><span class="mc-rx-flow-n">3</span> Registrar en ficha o manual</li>
                <li><span class="mc-rx-flow-n">4</span> Verificar pendientes</li>
            </ul>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("Guía para enfermería: sábana, cortina y registro manual", expanded=False):
            st.markdown(
                """
**Qué mirar primero**

- **Hora programada:** cuándo corresponde la dosis según la indicación.
- **Hora real** y **Registrado por:** cuándo se administró o dejó constancia y qué profesional lo cargó (incluye matrícula si está en el usuario). Así se ve si ya está **administrada** o sigue pendiente.
- **Seguridad del medicamento:** antes de registrar, revisá identidad del paciente y los **cinco correctos** (paciente, medicamento, dosis, vía, momento); el expander en la cortina resume el marco internacional y legal.

**Cuándo usar la cortina (tabla con hora libre)**

- Está **arriba de las tarjetas**: panel **«Cortina de medicación»** con vista en **verde / rojo / ámbar** y **quién registró**.
- Podés elegir **hora real (HH:MM)** distinta de la programada (paciente ausente, procedimiento, etc.) y marcar **No realizada** con **justificación** en la misma tabla.
- La cortina no reemplaza la **tabla de medicación** ni las tarjetas: ahí sigue el detalle completo.

**Si el paciente no está en el horario** (estudio, traslado, procedimiento externo, etc.)

- Es **habitual** que el esquema se ajuste al día. Registrá la situación con criterio institucional: muchas veces hace falta **registro manual** eligiendo el **horario programado** correcto o dejando constancia en **observación / justificación**.
- Si la prescripción debe cambiar de fondo (nueva pauta), corresponde **coordinación con medicina** o quien suspenda/edite la indicación según el rol.

**Si no se administra** (procedimiento que lo impide, intolerancia, rechazo, ayuno, etc.)

- No use solo la tilde de “realizada”. Vaya a **Registro manual** → estado **No realizada / Suspendida** y complete la **justificación clínica** (obligatoria).

**Grilla 24 h**

- Atajo para marcar varias horas seguidas; en celular suele ser más cómodo el formulario manual o las tarjetas compactas.
                """
            )
        fecha_hoy = ahora().strftime("%d/%m/%Y")
        admin_hoy = [
            a
            for a in st.session_state.get("administracion_med_db", [])
            if a.get("paciente") == paciente_sel and a.get("fecha") == fecha_hoy
        ]
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
        c_res1, c_res2, c_res3 = st.columns(3)
        c_res1.metric("Realizadas", int((plan_dia_df.get("Estado") == "Realizada").sum()) if not plan_dia_df.empty else 0)
        c_res2.metric(
            "No realizadas",
            int(plan_dia_df["Estado"].astype(str).str.contains("No realizada", case=False, na=False).sum())
            if not plan_dia_df.empty
            else 0,
        )
        c_res3.metric("Pendientes", int((plan_dia_df.get("Estado") == "Pendiente").sum()) if not plan_dia_df.empty else 0)

        st.markdown(
            '<p class="mc-rx-turno-hint">Elegí el formato que mejor se adapte al dispositivo; la información y el respaldo legal son los mismos.</p>',
            unsafe_allow_html=True,
        )
        vista_guardia = st.radio(
            "Formato de lectura del turno",
            ["Compacta para celular", "Tabla completa"],
            horizontal=True,
            index=0,
            key=f"recetas_vista_guardia_{paciente_sel}",
        )

        _render_bloque_cortina_medicacion(
            plan_dia_df,
            columnas_tabla,
            paciente_sel,
            mi_empresa,
            user,
            fecha_hoy,
            puede_registrar_dosis,
        )

        if vista_guardia == "Compacta para celular":
            st.caption(
                "Vista liviana para teléfonos viejos: cada tarjeta permite **hora real libre** y **no realizada** con justificación, además de la cortina arriba."
            )
            _render_sabana_compacta(plan_dia_df, paciente_sel, mi_empresa, user, fecha_hoy, puede_registrar_dosis)
            with st.expander("Ver tabla corta de apoyo"):
                mostrar_dataframe_con_scroll(tabla_guardia_df, height=260)
            with st.expander("Ver resumen por indicación"):
                mostrar_dataframe_con_scroll(sabana_resumen_df, height=240)
        else:
            st.caption("Tabla operativa de medicación con columnas más cortas y lectura más limpia.")
            mostrar_dataframe_con_scroll(tabla_guardia_df, height=340)
            with st.expander("Ver detalle completo de la guardia"):
                mostrar_dataframe_con_scroll(tabla_guardia_detallada_df, height=320)
            with st.expander("Ver resumen por indicación"):
                mostrar_dataframe_con_scroll(sabana_resumen_df, height=260)

        if puede_registrar_dosis and matriz_registro_rows:
            abrir_grilla_mar = st.checkbox(
                "Mostrar grilla 24 h para marcar varias dosis (pesada en celulares; preferi el formulario abajo)",
                value=False,
                key=f"abrir_grilla_mar_{paciente_sel}_{fecha_hoy}",
            )
            if abrir_grilla_mar:
                st.caption("Tildado rápido desde la sábana de medicación")
                st.caption(
                    "Marcá solo el casillero de la fila y la hora correspondiente. Al guardar se registra la hora real y el usuario."
                )
                columnas_mar = ["Prescripcion"] + horas_mar + ["A demanda"]
                matriz_registro_df = pd.DataFrame(matriz_registro_rows)
                matriz_registro_df["Prescripcion"] = matriz_registro_df.apply(
                    lambda fila: "\n".join(
                        [
                            str(fila.get("Indicacion", "") or "").strip(),
                            " | ".join(
                                [
                                    valor
                                    for valor in [
                                        str(fila.get("Via", "") or "").strip(),
                                        str(fila.get("Frecuencia", "") or "").strip(),
                                    ]
                                    if valor
                                ]
                            ),
                            str(fila.get("Detalle", "") or "").strip(),
                        ]
                    ).strip(),
                    axis=1,
                )
                matriz_registro_df = matriz_registro_df[columnas_mar]
                for hora_col in horas_mar + ["A demanda"]:
                    matriz_registro_df[hora_col] = matriz_registro_df[hora_col].astype("boolean")

                column_config = {
                    "Prescripcion": st.column_config.TextColumn("Prescripción / vía / frecuencia", width="large"),
                }
                for hora_col in horas_mar + ["A demanda"]:
                    column_config[hora_col] = st.column_config.CheckboxColumn(hora_col, width="small")

                editor_mar_df = st.data_editor(
                    matriz_registro_df,
                    hide_index=True,
                    width="stretch",
                    disabled=["Prescripcion"],
                    column_config=column_config,
                    key=f"matriz_mar_editor_{paciente_sel}_{fecha_hoy}",
                )

                if st.button(
                    "Guardar sábana de medicación (tildes)",
                    width="stretch",
                    key=f"guardar_mar_{paciente_sel}_{fecha_hoy}",
                ):
                    registros_guardados = 0
                    for row_idx in range(len(editor_mar_df)):
                        for hora_col in horas_mar + ["A demanda"]:
                            original_valor = matriz_registro_df.at[row_idx, hora_col]
                            nuevo_valor = editor_mar_df.at[row_idx, hora_col]

                            if pd.isna(original_valor):
                                continue
                            if bool(original_valor):
                                continue
                            if pd.isna(nuevo_valor) or not bool(nuevo_valor):
                                continue

                            meta = matriz_registro_map.get((row_idx, hora_col))
                            if not meta:
                                continue

                            nombre_med = str(meta.get("medicamento", "") or "").strip()
                            horario_sel = str(meta.get("horario_programado", "") or "").strip()
                            if not nombre_med:
                                continue

                            _guardar_administracion_medicacion(
                                paciente_sel,
                                mi_empresa,
                                user,
                                nombre_med,
                                fecha_hoy,
                                horario_sel,
                                "Realizada",
                            )
                            registros_guardados += 1

                    if registros_guardados:
                        guardar_datos()
                        st.success(f"Se guardaron {registros_guardados} administraciones desde la sábana 24 h.")
                        st.rerun()
                    else:
                        st.info("No hay nuevos horarios tildados para guardar.")

        st.markdown(
            '<h4 class="mc-rx-table-zone-title">Tabla de medicación indicada</h4>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Vista de referencia de la pauta. En celular, tarjetas con scroll interno; tabla ancha opcional con desliz horizontal."
        )
        if not plan_dia_df.empty:
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
                "Mostrar tabla ancha (deslizar horizontalmente; en iPhone suele ir mejor la vista tarjetas)",
                value=False,
                key=f"mostrar_tabla_plan_{paciente_sel}_{fecha_hoy}",
            )
            if mostrar_tabla_planilla:
                _render_tabla_clinica(
                    df_plan_visible,
                    key=f"plan_{paciente_sel}",
                    max_height=420 if not anticolapso_activo() else 320,
                    sticky_first_col=False,
                )
            else:
                _h_tarjetas_plan = 320 if anticolapso_activo() else 480
                with st.container(height=_h_tarjetas_plan):
                    _render_dataframe_filas_tarjetas(df_plan_visible)
        else:
            st.info("No hay medicación activa cargada para mostrar en la tabla de hoy.")

        if plan_hidratacion_rows:
            st.markdown(
                '<h4 class="mc-rx-table-zone-title">Plan de hidratación parenteral</h4>',
                unsafe_allow_html=True,
            )
            _render_tabla_clinica(
                pd.DataFrame(plan_hidratacion_rows),
                key=f"hidra_{paciente_sel}",
                max_height=320,
                sticky_first_col=False,
            )

        if sabana_resumen:
            st.caption("Resumen operativo de indicaciones activas")
            _render_tabla_clinica(
                pd.DataFrame(sabana_resumen),
                key=f"resumen_{paciente_sel}",
                max_height=260,
                sticky_first_col=False,
            )

        if puede_registrar_dosis:
            if vista_guardia == "Compacta para celular":
                st.caption(
                    "Si no se administró (procedimiento, intolerancia, paciente en estudio, etc.) o debe quedar otra hora, "
                    "usá **Registro manual** con estado y justificación."
                )
                registro_container = st.expander(
                    "Registro manual / no realizada / otro horario", expanded=False
                )
            else:
                registro_container = st.container()
            with registro_container:
                st.markdown(
                    """
                    <div class="mc-rx-form-shell">
                        <p class="mc-rx-form-shell-title">Registro manual con respaldo legal</p>
                        <p class="mc-rx-form-shell-sub">
                            Usalo cuando la cortina o la ficha no alcanzan: el sistema exige estado coherente y
                            justificación si la dosis no se administró. Queda asociado a tu usuario y sellado en tiempo.
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.form("form_registro_dosis", clear_on_submit=True):
                    c_med, c_hora = st.columns([2, 1])
                    opciones_recetas = list(range(len(recs_activas)))
                    receta_idx = c_med.selectbox(
                        "Medicacion a registrar",
                        opciones_recetas,
                        format_func=lambda idx: _etiqueta_receta(recs_activas[idx]),
                    )
                    receta_actual = recs_activas[receta_idx]
                    c_med.caption(f"Horarios: {format_horarios_receta(receta_actual)}")
                    horarios_receta = obtener_horarios_receta(receta_actual)
                    opciones_hora = horarios_receta or [f"{i:02d}:00" for i in range(24)]
                    hora_actual_str = f"{ahora().hour:02d}:00"
                    idx_hora = opciones_hora.index(hora_actual_str) if hora_actual_str in opciones_hora else 0
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
                            st.success(f"Registro guardado para el horario {hora_sel}.")
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
            c_ed1, c_ed2 = st.columns([3, 2])
            opciones_recetas = list(range(len(recs_activas)))
            receta_idx = c_ed1.selectbox(
                "Seleccionar indicacion",
                opciones_recetas,
                format_func=lambda idx: _etiqueta_receta(recs_activas[idx]),
                key=f"recetas_editar_sel_{paciente_sel}",
            )
            receta_objetivo = recs_activas[receta_idx]
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
                    guardar_datos()
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
                        if r.get("tipo_indicacion") == "Infusion / hidratacion":
                            detalle_inf = []
                            if r.get("velocidad_ml_h") not in ("", None):
                                detalle_inf.append(f"Velocidad: {r.get('velocidad_ml_h')} ml/h")
                            if r.get("alternar_con"):
                                detalle_inf.append(f"Alternar con: {r.get('alternar_con')}")
                            if detalle_inf:
                                c_info.caption(" | ".join(detalle_inf))
                            if r.get("plan_hidratacion"):
                                c_info.caption(f"Plan de hidratacion: {_resumen_plan_hidratacion(r.get('plan_hidratacion', []))}")
                            if r.get("detalle_infusion"):
                                c_info.caption(f"Indicacion complementaria: {r.get('detalle_infusion')}")
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
                                    width="stretch",
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
                                width="stretch",
                            )
        else:
            st.caption("Historial diferido para mejorar velocidad en telefonos viejos. Activalo solo si necesitas revisar indicaciones anteriores.")
