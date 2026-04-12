import base64
import io
import os
from datetime import time as dt_time
from html import escape

import pandas as pd
import streamlit as st

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
        return "✅"
    if "no realizada" in estado_norm or "suspendida" in estado_norm:
        return "❌"
    return "⏳"


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


def _hora_a_minutos(valor):
    texto = str(valor or "").strip()
    if not texto or texto == "A demanda":
        return 9999
    try:
        horas, minutos = texto.split(":")
        return (int(horas) * 60) + int(minutos)
    except Exception:
        return 9999


def _obtener_registro_administracion(admin_hoy, nombre_med, horario_programado=""):
    horario_programado = str(horario_programado or "").strip()
    for registro in admin_hoy:
        if registro.get("med") != nombre_med:
            continue

        horario_registrado = str(registro.get("horario_programado") or registro.get("hora") or "").strip()
        if horario_programado:
            if horario_registrado == horario_programado or str(registro.get("hora") or "").strip() == horario_programado:
                return registro
        else:
            if horario_registrado in {"", "A demanda"}:
                return registro
    return None


def _obtener_velocidad_horaria_infusion(registro, horario=""):
    horario = str(horario or "").strip()
    plan = registro.get("plan_hidratacion", []) or []
    for item in plan:
        if str(item.get("Hora sugerida", "")).strip() == horario:
            velocidad = item.get("Velocidad (ml/h)")
            if velocidad not in ("", None):
                return velocidad

    velocidad = registro.get("velocidad_ml_h")
    if velocidad not in ("", None):
        return velocidad
    return None


def _detalle_horario_infusion(registro, horario):
    if registro.get("tipo_indicacion") != "Infusion / hidratacion":
        return registro.get("detalle_infusion", "")

    partes = []
    solucion = str(registro.get("solucion", "") or "").strip()
    alternar_con = str(registro.get("alternar_con", "") or "").strip()
    velocidad = _obtener_velocidad_horaria_infusion(registro, horario)

    if solucion:
        partes.append(solucion)
    if velocidad not in ("", None):
        partes.append(f"{velocidad} ml/h")
    if alternar_con:
        partes.append(f"Alternar con {alternar_con}")

    if partes:
        return " | ".join(partes)
    return registro.get("detalle_infusion", "")


def _texto_celda_mar(horario_programado, estado, hora_realizada="", observacion=""):
    horario_programado = str(horario_programado or "").strip()
    hora_realizada = str(hora_realizada or "").strip()
    observacion = str(observacion or "").strip()
    estado_legible = _estado_legible(estado)

    if estado_legible == "Realizada":
        texto = f"OK {hora_realizada}".strip()
    elif estado_legible == "No realizada":
        texto = "NO"
    else:
        texto = "PEND"

    if observacion and estado_legible == "No realizada":
        texto = f"{texto} | {observacion}"

    return f"{horario_programado} {texto}".strip() if horario_programado and horario_programado != "A demanda" else texto


def _css_safe_key(key):
    safe_key = "".join(ch if str(ch).isalnum() else "_" for ch in str(key or "tabla"))
    return safe_key or "tabla"


def _render_tabla_clinica(
    df,
    key,
    max_height=360,
    sticky_first_col=True,
    compact=False,
    nowrap_cells=True,
):
    if df is None or df.empty:
        return

    safe_key = _css_safe_key(key)
    # Tabla ancha + scroll horizontal; nowrap evita guiones tipo "Medica-cion" en Safari iOS.
    table_width = "max-content"
    table_layout = "auto"
    cell_ws = "nowrap" if nowrap_cells else "normal"
    header_padding = "9px 8px" if compact else "12px 10px"
    cell_padding = "7px 8px" if compact else "10px 10px"
    font_size = "0.80rem" if compact else "0.92rem"
    sticky_min_width = "220px" if compact else "260px"
    sticky_max_width = "280px" if compact else "340px"
    cell_min = "72px" if compact else "6rem"

    clases_th = []
    clases_td = []
    for idx, _ in enumerate(df.columns):
        clases_th.append(' class="mc-table-sticky"' if sticky_first_col and idx == 0 else "")
        clases_td.append(' class="mc-table-sticky"' if sticky_first_col and idx == 0 else "")

    html = [
        f"""
        <style>
            .mc-table-shell-{safe_key} {{
                width: 100% !important;
                max-width: 100% !important;
                overflow-x: auto !important;
                overflow-y: auto !important;
                -webkit-overflow-scrolling: touch !important;
                max-height: {max_height}px;
                border: 1px solid rgba(148, 163, 184, 0.18);
                border-radius: 18px;
                background: rgba(7, 14, 28, 0.9);
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
            }}
            .mc-table-shell-{safe_key} table {{
                width: max-content !important;
                min-width: 100% !important;
                max-width: none !important;
                table-layout: auto !important;
                border-collapse: separate !important;
                border-spacing: 0 !important;
                font-size: {font_size};
                hyphens: none !important;
                -webkit-hyphens: none !important;
            }}
            .mc-table-shell-{safe_key} thead th {{
                position: sticky;
                top: 0;
                z-index: 3;
                background: #1f2533;
                color: #e5eefc;
                padding: {header_padding};
                text-align: left;
                border-bottom: 1px solid rgba(148, 163, 184, 0.18);
                border-right: 1px solid rgba(148, 163, 184, 0.12);
                white-space: nowrap !important;
                hyphens: none !important;
                -webkit-hyphens: none !important;
                word-break: normal !important;
                overflow-wrap: normal !important;
                line-height: 1.25;
            }}
            .mc-table-shell-{safe_key} tbody td {{
                padding: {cell_padding};
                color: #f8fafc;
                border-bottom: 1px solid rgba(148, 163, 184, 0.10);
                border-right: 1px solid rgba(148, 163, 184, 0.08);
                vertical-align: top;
                white-space: {cell_ws} !important;
                hyphens: none !important;
                -webkit-hyphens: none !important;
                word-break: normal !important;
                overflow-wrap: normal !important;
                min-width: {cell_min} !important;
                max-width: none !important;
                line-height: 1.4;
                background: rgba(5, 10, 22, 0.98);
            }}
            .mc-table-shell-{safe_key} .mc-table-sticky {{
                position: sticky;
                left: 0;
                z-index: 2;
                background: #0a1020;
                min-width: {sticky_min_width};
                max-width: {sticky_max_width};
            }}
            .mc-table-shell-{safe_key} thead .mc-table-sticky {{
                z-index: 4;
                background: #26314b;
            }}
        </style>
        """
    ]
    html.append(
        f'<div class="mc-recetas-table-zone" style="overflow-x:auto;-webkit-overflow-scrolling:touch;width:100%;max-width:100%;">'
        f'<div class="mc-table-shell-{safe_key}"><table><thead><tr>'
    )
    for idx, col in enumerate(df.columns):
        html.append(f"<th{clases_th[idx]}>{escape(str(col))}</th>")
    html.append("</tr></thead><tbody>")

    for _, row in df.iterrows():
        html.append("<tr>")
        for idx, col in enumerate(df.columns):
            valor = row[col]
            if pd.isna(valor):
                texto = ""
            else:
                texto = escape(str(valor)).replace("\n", "<br>")
            html.append(f"<td{clases_td[idx]}>{texto}</td>")
        html.append("</tr>")
    html.append("</tbody></table></div></div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def _render_dataframe_filas_tarjetas(df):
    """Tarjetas sin st.expander: en movil el chevron de expander mostraba el texto _arrow_right (bug Streamlit / fuentes)."""
    if df is None or df.empty:
        return
    cols = list(df.columns)
    for _, row in df.iterrows():
        h = str(row.get("Hora", "") or "").strip()
        med = str(row.get("Medicacion", "") or "").strip()
        est = str(row.get("Estado", "") or "").strip()
        label = " · ".join(p for p in (h, med, est) if p) or "Dosis"
        with st.container(border=True):
            st.markdown(
                f'<p class="mc-rx-card-title">{escape(label)}</p>',
                unsafe_allow_html=True,
            )
            for col in cols:
                val = row.get(col, "")
                if pd.isna(val) or str(val).strip() == "":
                    continue
                v_html = escape(str(val).strip()).replace("\n", "<br/>")
                st.markdown(
                    f'<p class="mc-rx-card-line"><span class="mc-rx-card-k">{escape(str(col))}:</span> {v_html}</p>',
                    unsafe_allow_html=True,
                )


def _chips_estado_sabana(valor):
    chips = []
    for bloque in str(valor or "").split("\n"):
        bloque = bloque.strip()
        if not bloque:
            continue

        texto_upper = bloque.upper()
        if "OK" in texto_upper:
            _, _, detalle = bloque.partition("OK")
            chips.append(("ok", "OK", detalle.strip()))
        elif "NO" in texto_upper:
            _, _, detalle = bloque.partition("NO")
            chips.append(("no", "NO", detalle.strip(" |")))
        else:
            chips.append(("pend", "PEND", ""))
    return chips


def _render_sabana_prescripcion_visual(sabana_rows, horas_mar, key, hora_actual=""):
    if not sabana_rows:
        return

    safe_key = _css_safe_key(key)
    hora_actual = str(hora_actual or "").strip()
    columnas_horarias = list(horas_mar) + ["A demanda"]
    html = [
        f"""
        <style>
            .mc-sheet-shell-{safe_key} {{
                width: 100%;
                overflow: auto;
                max-height: 430px;
                border: 1px solid rgba(148, 163, 184, 0.18);
                border-radius: 20px;
                background: linear-gradient(180deg, rgba(10, 16, 30, 0.98) 0%, rgba(6, 10, 21, 0.98) 100%);
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
            }}
            .mc-sheet-shell-{safe_key} table {{
                width: max-content;
                min-width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                font-size: 0.82rem;
            }}
            .mc-sheet-shell-{safe_key} thead th {{
                position: sticky;
                top: 0;
                z-index: 6;
                padding: 10px 8px;
                background: #24304a;
                color: #e5eefc;
                text-align: center;
                border-bottom: 1px solid rgba(148, 163, 184, 0.20);
                border-right: 1px solid rgba(148, 163, 184, 0.12);
                white-space: nowrap;
            }}
            .mc-sheet-shell-{safe_key} tbody td {{
                min-width: 58px;
                max-width: 58px;
                padding: 7px 6px;
                text-align: center;
                vertical-align: middle;
                border-bottom: 1px solid rgba(148, 163, 184, 0.10);
                border-right: 1px solid rgba(148, 163, 184, 0.08);
                background: rgba(4, 9, 20, 0.98);
            }}
            .mc-sheet-shell-{safe_key} .mc-sheet-sticky {{
                position: sticky;
                z-index: 5;
            }}
            .mc-sheet-shell-{safe_key} .mc-sheet-val {{
                left: 0;
                min-width: 86px;
                max-width: 86px;
                background: #0b1326;
            }}
            .mc-sheet-shell-{safe_key} .mc-sheet-rx {{
                left: 86px;
                min-width: 360px;
                max-width: 360px;
                text-align: left;
                padding: 10px 12px;
                background: #091122;
            }}
            .mc-sheet-shell-{safe_key} thead .mc-sheet-rx {{
                text-align: left;
            }}
            .mc-sheet-shell-{safe_key} .mc-sheet-now {{
                background: rgba(245, 158, 11, 0.14) !important;
            }}
            .mc-sheet-shell-{safe_key} .mc-sheet-rx-title {{
                color: #f8fafc;
                font-weight: 700;
                font-size: 0.9rem;
                line-height: 1.28;
                margin-bottom: 0.2rem;
            }}
            .mc-sheet-shell-{safe_key} .mc-sheet-rx-meta {{
                color: #9db0c9;
                font-size: 0.75rem;
                line-height: 1.25;
                margin-bottom: 0.18rem;
            }}
            .mc-sheet-shell-{safe_key} .mc-sheet-rx-detail {{
                color: #cfe0f5;
                font-size: 0.74rem;
                line-height: 1.25;
            }}
            .mc-sheet-shell-{safe_key} .mc-sheet-badge {{
                display: inline-flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-width: 42px;
                min-height: 34px;
                border-radius: 10px;
                border: 1px solid rgba(148, 163, 184, 0.16);
                padding: 3px 4px;
                gap: 2px;
                font-size: 0.68rem;
                font-weight: 800;
                letter-spacing: 0.02em;
                background: rgba(15, 23, 42, 0.72);
                color: #dce8f9;
            }}
            .mc-sheet-shell-{safe_key} .mc-sheet-badge small {{
                font-size: 0.62rem;
                line-height: 1.1;
                font-weight: 600;
                color: inherit;
                opacity: 0.92;
            }}
            .mc-sheet-shell-{safe_key} .mc-sheet-badge-ok {{
                background: rgba(34, 197, 94, 0.16);
                border-color: rgba(34, 197, 94, 0.32);
                color: #dcfce7;
            }}
            .mc-sheet-shell-{safe_key} .mc-sheet-badge-no {{
                background: rgba(239, 68, 68, 0.15);
                border-color: rgba(239, 68, 68, 0.28);
                color: #fee2e2;
            }}
            .mc-sheet-shell-{safe_key} .mc-sheet-badge-pend {{
                background: rgba(245, 158, 11, 0.13);
                border-color: rgba(245, 158, 11, 0.24);
                color: #fde68a;
            }}
            .mc-sheet-shell-{safe_key} .mc-sheet-empty {{
                display: inline-block;
                width: 12px;
                height: 12px;
                border-radius: 999px;
                background: rgba(148, 163, 184, 0.12);
            }}
            .mc-sheet-shell-{safe_key} .mc-sheet-validada {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 68px;
                min-height: 28px;
                border-radius: 999px;
                background: rgba(56, 189, 248, 0.12);
                border: 1px solid rgba(56, 189, 248, 0.24);
                color: #d8f3ff;
                font-size: 0.72rem;
                font-weight: 700;
            }}
        </style>
        """
    ]
    html.append(f'<div class="mc-recetas-sabana-zone"><div class="mc-sheet-shell-{safe_key}"><table><thead><tr>')
    html.append('<th class="mc-sheet-sticky mc-sheet-val">Validada</th>')
    html.append('<th class="mc-sheet-sticky mc-sheet-rx">Prescripcion</th>')
    for hora_col in horas_mar:
        clase_hora = " mc-sheet-now" if hora_col == hora_actual else ""
        html.append(f'<th class="{clase_hora.strip()}">{escape(hora_col[:2])}</th>' if clase_hora else f"<th>{escape(hora_col[:2])}</th>")
    html.append('<th>A demanda</th>')
    html.append("</tr></thead><tbody>")

    for fila in sabana_rows:
        titulo = str(fila.get("Indicacion", "") or "").strip()
        via = str(fila.get("Via", "") or "").strip()
        frecuencia = str(fila.get("Frecuencia", "") or "").strip()
        detalle = str(fila.get("Detalle", "") or "").strip()

        html.append("<tr>")
        html.append('<td class="mc-sheet-sticky mc-sheet-val"><span class="mc-sheet-validada">Activa</span></td>')
        html.append(
            "<td class=\"mc-sheet-sticky mc-sheet-rx\">"
            f"<div class=\"mc-sheet-rx-title\">{escape(titulo)}</div>"
            f"<div class=\"mc-sheet-rx-meta\">{escape(' | '.join([valor for valor in [via, frecuencia] if valor]))}</div>"
            f"<div class=\"mc-sheet-rx-detail\">{escape(detalle or '-')}</div>"
            "</td>"
        )

        for hora_col in columnas_horarias:
            clases_celda = " mc-sheet-now" if hora_col == hora_actual else ""
            html.append(f'<td class="{clases_celda.strip()}">' if clases_celda else "<td>")
            chips = _chips_estado_sabana(fila.get(hora_col, ""))
            if chips:
                for estado_chip, etiqueta, detalle_chip in chips:
                    detalle_html = f"<small>{escape(detalle_chip)}</small>" if detalle_chip else ""
                    html.append(
                        f'<span class="mc-sheet-badge mc-sheet-badge-{estado_chip}">{escape(etiqueta)}{detalle_html}</span>'
                    )
            else:
                html.append('<span class="mc-sheet-empty"></span>')
            html.append("</td>")
        html.append("</tr>")

    html.append("</tbody></table></div></div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def _guardar_administracion_medicacion(
    paciente_sel,
    mi_empresa,
    user,
    nombre_med,
    fecha_hoy,
    horario_programado,
    estado,
    motivo="",
):
    hora_real = ahora().strftime("%H:%M")
    estado_guardado = "Realizada" if str(estado).strip().lower() == "realizada" else "No realizada"
    usuario_login = str(user.get("usuario_login", "") or "").strip().lower()

    st.session_state["administracion_med_db"] = [
        a
        for a in st.session_state.get("administracion_med_db", [])
        if not (
            a.get("paciente") == paciente_sel
            and a.get("fecha") == fecha_hoy
            and a.get("med") == nombre_med
            and (a.get("horario_programado") == horario_programado or a.get("hora") == horario_programado)
        )
    ]

    st.session_state["administracion_med_db"].append(
        {
            "paciente": paciente_sel,
            "med": nombre_med,
            "fecha": fecha_hoy,
            "hora": hora_real,
            "hora_realizada": hora_real,
            "horario_programado": horario_programado,
            "estado": estado_guardado,
            "motivo": motivo.strip() if estado_guardado != "Realizada" else "",
            "firma": user["nombre"],
            "actor_login": usuario_login,
            "actor_rol": user.get("rol", ""),
            "actor_perfil": user.get("perfil_profesional", ""),
            "empresa": mi_empresa,
            "modulo_origen": "Recetas",
            "fecha_hora_registro": ahora().strftime("%d/%m/%Y %H:%M:%S"),
        }
    )
    return estado_guardado, hora_real


def _auditar_recetas(
    paciente_sel,
    user,
    accion,
    detalle,
    referencia="",
    criticidad="media",
    extra=None,
    actor=None,
    matricula=None,
):
    registrar_auditoria_legal(
        "Medicacion",
        paciente_sel,
        accion,
        actor or user.get("nombre", "Sistema"),
        matricula if matricula is not None else user.get("matricula", ""),
        detalle,
        referencia=referencia,
        extra=extra or {},
        usuario=user,
        modulo="Recetas",
        criticidad=criticidad,
    )


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
            tipo_indicacion = st.radio(
                "Tipo de indicacion",
                ["Medicacion", "Infusion / hidratacion"],
                horizontal=False,
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
                    n_h = len(horarios_sugeridos)
                    st.caption(f"Horarios sugeridos para la guardia: {n_h} horario(s).")
                    if n_h > 10:
                        if st.checkbox(
                            "Ver lista completa de horarios sugeridos",
                            value=False,
                            key="ver_lista_horarios_receta_med",
                        ):
                            st.text("\n".join(horarios_sugeridos))
                    else:
                        st.caption(" ".join(horarios_sugeridos))
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
                        mostrar_dataframe_con_scroll(pd.DataFrame(plan_hidratacion), height=220)
                        horarios_sugeridos = [item["Hora sugerida"] for item in plan_hidratacion]
                    else:
                        horarios_sugeridos = [hora_inicio.strftime("%H:%M")]
                else:
                    horarios_sugeridos = [hora_inicio.strftime("%H:%M")]
                    st.caption(
                        "Referencia general de bomba: ml/h = volumen total (ml) / tiempo (h). "
                        "Verificar siempre con protocolo institucional y criterio medico."
                    )
                n_vis = len(horarios_sugeridos)
                st.caption(f"Horarios visibles en la sabana diaria: {n_vis} horario(s).")
                if n_vis > 10:
                    if st.checkbox(
                        "Ver lista de horarios en sabana (infusion)",
                        value=False,
                        key="ver_horarios_sabana_infusion_receta",
                    ):
                        st.text("\n".join(horarios_sugeridos))
                else:
                    st.caption(" ".join(horarios_sugeridos))

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
                    horizontal=False,
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
                        descripcion_guardada = med_final if tipo_indicacion == "Medicacion" else (solucion or "Infusion / hidratacion")
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
                                "tipo_indicacion": tipo_indicacion,
                                "solucion": solucion,
                                "volumen_ml": volumen_ml,
                                "velocidad_ml_h": velocidad_ml_h,
                                "alternar_con": alternar_con,
                                "detalle_infusion": detalle_infusion,
                                "plan_hidratacion": plan_hidratacion,
                                "fecha_estado": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                                "profesional_estado": user["nombre"],
                                "matricula_estado": medico_matricula.strip(),
                                "origen_registro": "Prescripcion digital",
                                "empresa": mi_empresa,
                            }
                        )
                        _auditar_recetas(
                            paciente_sel,
                            user,
                            "Indicacion medica registrada",
                            texto_receta,
                            referencia=texto_receta[:80],
                            criticidad="alta",
                            extra={
                                "tipo_indicacion": tipo_indicacion,
                                "frecuencia": frecuencia,
                                "horarios_programados": " | ".join(horarios_sugeridos),
                                "origen_registro": "Prescripcion digital",
                                "firma_digital": bool(firma_b64),
                            },
                            actor=medico_nombre.strip() or user.get("nombre", ""),
                            matricula=medico_matricula.strip(),
                        )
                        guardar_datos()
                        st.success(f"Prescripcion de {descripcion_guardada} guardada con firma medica.")
                        st.rerun()

    if puede_cargar_papel:
        abrir_papel_receta = st.checkbox(
            "Mostrar: cargar indicacion medica en papel o PDF",
            value=False,
            key=f"abrir_papel_receta_{paciente_sel}",
        )
        if abrir_papel_receta:
            with st.container(border=True):
                st.caption(
                    "Usa esta opcion cuando el medico deja una indicacion firmada en papel o PDF y queres dejarla trazable en el sistema."
                )
                tipo_indicacion_papel = st.radio(
                    "Tipo de indicacion a cargar",
                    ["Medicacion", "Infusion / hidratacion"],
                    horizontal=False,
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
                            mostrar_dataframe_con_scroll(pd.DataFrame(plan_papel), height=220)
                            horarios_papel = [item["Hora sugerida"] for item in plan_papel]
                    if not horarios_papel:
                        horarios_papel = [hora_papel.strftime("%H:%M")]
                    st.caption(f"Horarios visibles en la sabana diaria: {' | '.join(horarios_papel)}")
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
                            "firmado_por": user["nombre"],
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
                            "profesional_estado": user["nombre"],
                            "matricula_estado": user.get("matricula", ""),
                            "origen_registro": "Indicacion medica en papel",
                            "adjunto_papel_b64": adjunto_b64,
                            "adjunto_papel_nombre": adjunto_nombre,
                            "adjunto_papel_tipo": adjunto_tipo,
                            "empresa": mi_empresa,
                        }
                        st.session_state["indicaciones_db"].append(registro)
                        _auditar_recetas(
                            paciente_sel,
                            user,
                            "Indicacion medica en papel cargada",
                            f"Medico: {medico_papel.strip()} | Matricula: {matricula_papel.strip()} | {detalle_papel.strip()}",
                            referencia=detalle_papel.strip()[:80],
                            criticidad="alta",
                            extra={
                                "tipo_indicacion": tipo_indicacion_papel,
                                "frecuencia": frecuencia_papel,
                                "origen_registro": "Indicacion medica en papel",
                                "adjunto_respaldo": bool(adjunto_b64),
                                "medico_indicado": medico_papel.strip(),
                                "matricula_indicada": matricula_papel.strip(),
                            },
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
        plan_hidratacion_rows = []
        for r in recs_activas[:40]:
            partes = r["med"].split(" | ")
            nombre = _extraer_nombre_medicacion(r.get("med", ""))
            via_texto = partes[1].replace("Via: ", "") if len(partes) > 1 and "Via:" in partes[1] else r.get("via", "")
            frecuencia_texto = r.get("frecuencia") or (partes[2] if len(partes) > 2 else "")
            horarios = obtener_horarios_receta(r)
            horarios_legibles = format_horarios_receta(r)
            velocidad_base = _obtener_velocidad_horaria_infusion(r, horarios[0] if horarios else "")
            if r.get("tipo_indicacion") == "Infusion / hidratacion":
                plan_hidratacion_rows.append(
                    {
                        "Solucion": r.get("solucion", "") or nombre,
                        "Volumen (ml)": int(r.get("volumen_ml", 0)) if r.get("volumen_ml") not in ("", None, 0) else "",
                        "ML/h": velocidad_base if velocidad_base not in ("", None) else "",
                        "Horarios": horarios_legibles,
                        "Plan": _resumen_plan_hidratacion(r.get("plan_hidratacion", [])) or "Continua / fija",
                        "Alternar con": r.get("alternar_con", "") or "-",
                        "Indicacion": r.get("detalle_infusion", "") or "-",
                    }
                )
            sabana_resumen.append(
                {
                    "Medicamento": nombre,
                    "Via": via_texto or "S/D",
                    "Frecuencia": frecuencia_texto or "S/D",
                    "Horarios": horarios_legibles,
                    "Detalle": _detalle_horario_infusion(r, horarios[0] if horarios else "") or "-",
                    "Estado": r.get("estado_receta", "Activa"),
                }
            )

            if horarios:
                for horario in horarios:
                    admin_reg = _obtener_registro_administracion(admin_hoy, nombre, horario)
                    estado_actual = admin_reg.get("estado", "Pendiente") if admin_reg else "Pendiente"
                    velocidad_horaria = _obtener_velocidad_horaria_infusion(r, horario)
                    item_dia = {
                        "OK": _estado_icono(estado_actual),
                        "Hora programada": horario,
                        "Hora realizada": admin_reg.get("hora", "") if admin_reg else "",
                        "Medicamento": nombre,
                        "Detalle / velocidad": _detalle_horario_infusion(r, horario),
                        "Via": via_texto or "S/D",
                        "Frecuencia": frecuencia_texto or "S/D",
                        "Estado": _estado_legible(estado_actual),
                        "Observacion": admin_reg.get("motivo", "") if admin_reg else "",
                        "Registrado por": admin_reg.get("firma", "") if admin_reg else "",
                    }
                    if r.get("tipo_indicacion") == "Infusion / hidratacion":
                        item_dia["Solucion"] = r.get("solucion", "") or "-"
                        item_dia["ML/h"] = velocidad_horaria if velocidad_horaria not in ("", None) else "-"
                    plan_dia.append(item_dia)
            else:
                admin_reg = _obtener_registro_administracion(admin_hoy, nombre)
                estado_actual = admin_reg.get("estado", "Pendiente") if admin_reg else "Pendiente"
                item_dia = {
                    "OK": _estado_icono(estado_actual),
                    "Hora programada": "A demanda",
                    "Hora realizada": admin_reg.get("hora", "") if admin_reg else "",
                    "Medicamento": nombre,
                    "Detalle / velocidad": _detalle_horario_infusion(r, ""),
                    "Via": via_texto or "S/D",
                    "Frecuencia": frecuencia_texto or "A demanda",
                    "Estado": _estado_legible(estado_actual),
                    "Observacion": admin_reg.get("motivo", "") if admin_reg else "",
                    "Registrado por": admin_reg.get("firma", "") if admin_reg else "",
                }
                if r.get("tipo_indicacion") == "Infusion / hidratacion":
                    item_dia["Solucion"] = r.get("solucion", "") or "-"
                    item_dia["ML/h"] = velocidad_base if velocidad_base not in ("", None) else "-"
                plan_dia.append(item_dia)

        plan_dia_df = pd.DataFrame(plan_dia)
        if not plan_dia_df.empty:
            plan_dia_df["_orden"] = plan_dia_df["Hora programada"].apply(_hora_a_minutos)
            plan_dia_df = plan_dia_df.sort_values(by=["_orden", "Medicamento"]).drop(columns=["_orden"])

        c_res1, c_res2, c_res3 = st.columns(3)
        c_res1.metric("Realizadas", int((plan_dia_df.get("Estado") == "Realizada").sum()) if not plan_dia_df.empty else 0)
        c_res2.metric("No realizadas", int((plan_dia_df.get("Estado") == "No realizada").sum()) if not plan_dia_df.empty else 0)
        c_res3.metric("Pendientes", int((plan_dia_df.get("Estado") == "Pendiente").sum()) if not plan_dia_df.empty else 0)
        st.caption(
            "En telefonos viejos o con poca RAM: preferi el formulario Registrar dosis (mas abajo); "
            "las grillas con muchas columnas estan en secciones colapsables."
        )

        columnas_tabla = [
            col
            for col in [
                "Hora programada",
                "Medicamento",
                "Solucion",
                "ML/h",
                "Detalle / velocidad",
                "Via",
                "Frecuencia",
                "Estado",
                "Hora realizada",
                "Observacion",
                "Registrado por",
            ]
            if col in plan_dia_df.columns
        ]

        horas_mar = [f"{hora:02d}:00" for hora in range(24)]
        sabana_mar_rows = []
        sabana_mar_map = {}
        matriz_registro_rows = []
        matriz_registro_map = {}
        matriz_registro_index = {}
        for item in plan_dia_df.to_dict("records") if not plan_dia_df.empty else []:
            clave_mar = (
                str(item.get("Medicamento", "")),
                str(item.get("Via", "")),
                str(item.get("Frecuencia", "")),
                str(item.get("Detalle / velocidad", "")),
            )
            if clave_mar not in sabana_mar_map:
                fila_mar = {
                    "Indicacion": item.get("Medicamento", ""),
                    "Via": item.get("Via", ""),
                    "Frecuencia": item.get("Frecuencia", ""),
                    "Detalle": item.get("Detalle / velocidad", ""),
                }
                for hora_col in horas_mar:
                    fila_mar[hora_col] = ""
                fila_mar["A demanda"] = ""
                sabana_mar_map[clave_mar] = fila_mar
                sabana_mar_rows.append(fila_mar)

                fila_registro = {
                    "Indicacion": item.get("Medicamento", ""),
                    "Via": item.get("Via", ""),
                    "Frecuencia": item.get("Frecuencia", ""),
                    "Detalle": item.get("Detalle / velocidad", ""),
                }
                for hora_col in horas_mar:
                    fila_registro[hora_col] = pd.NA
                fila_registro["A demanda"] = pd.NA
                matriz_registro_index[clave_mar] = len(matriz_registro_rows)
                matriz_registro_rows.append(fila_registro)

            horario_programado = str(item.get("Hora programada", "") or "").strip()
            columna_hora = "A demanda" if horario_programado == "A demanda" else f"{int(horario_programado.split(':')[0]):02d}:00"
            texto_celda = _texto_celda_mar(
                horario_programado,
                item.get("Estado", ""),
                item.get("Hora realizada", ""),
                item.get("Observacion", ""),
            )
            valor_actual = sabana_mar_map[clave_mar].get(columna_hora, "")
            sabana_mar_map[clave_mar][columna_hora] = (
                f"{valor_actual}\n{texto_celda}".strip() if valor_actual else texto_celda
            )

            fila_registro = matriz_registro_rows[matriz_registro_index[clave_mar]]
            fila_registro[columna_hora] = item.get("Estado") == "Realizada"
            matriz_registro_map[(matriz_registro_index[clave_mar], columna_hora)] = {
                "medicamento": item.get("Medicamento", ""),
                "horario_programado": horario_programado,
                "estado": item.get("Estado", ""),
            }

        if sabana_mar_rows:
            st.markdown("#### Prescripcion y sabana 24 hs")
            st.caption("Vista horizontal tipo enfermeria para leer rapido que esta indicado, que ya se administro y que sigue pendiente.")
            _render_sabana_prescripcion_visual(
                sabana_mar_rows,
                horas_mar,
                key=f"mar_visual_{paciente_sel}",
                hora_actual=f"{ahora().hour:02d}:00",
            )
        else:
            st.info("No se pudo construir la sabana 24 hs con las indicaciones activas.")

        if puede_registrar_dosis and matriz_registro_rows:
            abrir_grilla_mar = st.checkbox(
                "Mostrar grilla 24 h para marcar varias dosis (pesada en celulares; preferi el formulario abajo)",
                value=False,
                key=f"abrir_grilla_mar_{paciente_sel}_{fecha_hoy}",
            )
            if abrir_grilla_mar:
                st.caption("Tildado rapido desde la sabana")
                st.caption(
                    "Marca solo los casilleros de la fila y la hora correspondiente. Al guardar se registra la hora real y el usuario."
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
                    "Prescripcion": st.column_config.TextColumn("Prescripcion", width="large"),
                }
                for hora_col in horas_mar + ["A demanda"]:
                    column_config[hora_col] = st.column_config.CheckboxColumn(hora_col, width="small")

                editor_mar_df = st.data_editor(
                    matriz_registro_df,
                    hide_index=True,
                    use_container_width=True,
                    disabled=["Prescripcion"],
                    column_config=column_config,
                    key=f"matriz_mar_editor_{paciente_sel}_{fecha_hoy}",
                )

                if st.button("Guardar sabana tipo prescripcion", use_container_width=True, key=f"guardar_mar_{paciente_sel}_{fecha_hoy}"):
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
                            _auditar_recetas(
                                paciente_sel,
                                user,
                                "Registro de administracion desde sabana 24 hs",
                                f"{nombre_med} | Horario: {horario_sel or 'A demanda'} | Estado: Realizada",
                                referencia=nombre_med,
                                criticidad="alta",
                                extra={
                                    "horario_programado": horario_sel or "A demanda",
                                    "estado_administracion": "Realizada",
                                    "origen_registro": "Sabana 24 hs",
                                },
                            )
                            registros_guardados += 1

                    if registros_guardados:
                        guardar_datos()
                        st.success(f"Se guardaron {registros_guardados} administraciones desde la sabana 24 hs.")
                        st.rerun()
                    else:
                        st.info("No hay nuevos horarios tildados para guardar.")

        st.markdown("#### Tabla de medicacion indicada")
        st.caption("En celular se muestran tarjetas por defecto. La tabla ancha solo si la activas y deslizas.")
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
                    max_height=420,
                    sticky_first_col=False,
                )
            else:
                _render_dataframe_filas_tarjetas(df_plan_visible)
        else:
            st.info("No hay medicacion activa cargada para mostrar en la tabla de hoy.")

        if puede_registrar_dosis and not plan_dia_df.empty:
            pendientes_df = plan_dia_df[plan_dia_df["Estado"] != "Realizada"].copy().reset_index(drop=True)
            if not pendientes_df.empty:
                abrir_tabla_tildes = st.checkbox(
                    "Mostrar tabla detallada para tildar dosis (muchas columnas; mejor en tablet o PC)",
                    value=False,
                    key=f"abrir_tabla_tildes_{paciente_sel}_{fecha_hoy}",
                )
                if abrir_tabla_tildes:
                    st.caption("Tildar administracion desde la tabla")
                    pendientes_df.insert(0, "Administrada", False)
                    editor_columnas = ["Administrada"] + columnas_tabla
                    editor_df = st.data_editor(
                        pendientes_df[editor_columnas],
                        hide_index=True,
                        use_container_width=True,
                        disabled=[col for col in editor_columnas if col != "Administrada"],
                        column_config={
                            "Administrada": st.column_config.CheckboxColumn(
                                "Tildar",
                                help="Marca la indicacion como realizada y guarda la hora real.",
                                default=False,
                            )
                        },
                        key=f"cortina_tabla_editor_{paciente_sel}_{fecha_hoy}",
                    )

                    if st.button(
                        "Guardar tildes de la tabla",
                        use_container_width=True,
                        key=f"guardar_tildes_cortina_{paciente_sel}",
                    ):
                        registros_guardados = 0
                        for idx, fila in editor_df.iterrows():
                            if not bool(fila.get("Administrada")):
                                continue

                            horario_sel = str(fila.get("Hora programada", "") or "").strip()
                            nombre_med = str(fila.get("Medicamento", "") or "").strip()
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
                            _auditar_recetas(
                                paciente_sel,
                                user,
                                "Registro de administracion desde tabla de cortina",
                                f"{nombre_med} | Horario: {horario_sel or 'A demanda'} | Estado: Realizada",
                                referencia=nombre_med,
                                criticidad="alta",
                                extra={
                                    "horario_programado": horario_sel or "A demanda",
                                    "estado_administracion": "Realizada",
                                    "origen_registro": "Tabla de cortina",
                                },
                            )
                            registros_guardados += 1

                        if registros_guardados:
                            guardar_datos()
                            st.success(f"Se guardaron {registros_guardados} administraciones desde la tabla.")
                            st.rerun()
                        else:
                            st.info("Marca al menos una indicacion para guardar.")
            else:
                st.caption("Todas las indicaciones de hoy ya figuran como realizadas.")

        if plan_hidratacion_rows:
            st.markdown("#### Plan de hidratacion parenteral")
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
                estado_sel = st.radio("Estado", ["Realizada", "No realizada / Suspendida"], horizontal=False)
                justificacion = st.text_input("Justificacion clinica")
                if st.form_submit_button("Guardar registro", use_container_width=True):
                    if "No realizada" in estado_sel and not justificacion.strip():
                        st.error("Es obligatorio justificar por que no se administro la dosis.")
                    else:
                        nombre_med = receta_actual["med"].split(" |")[0].strip()
                        _guardar_administracion_medicacion(
                            paciente_sel,
                            mi_empresa,
                            user,
                            nombre_med,
                            fecha_hoy,
                            hora_sel,
                            estado_sel,
                            justificacion,
                        )
                        _auditar_recetas(
                            paciente_sel,
                            user,
                            "Registro de administracion",
                            f"{nombre_med} | Horario: {hora_sel} | Estado: {estado_sel}",
                            referencia=nombre_med,
                            criticidad="alta",
                            extra={
                                "horario_programado": hora_sel,
                                "estado_administracion": estado_sel,
                                "justificacion": justificacion.strip(),
                                "origen_registro": "Carga manual",
                            },
                        )
                        guardar_datos()
                        st.success(f"Registro guardado para el horario {hora_sel}.")
                        st.rerun()
        else:
            st.caption("El registro de administracion queda deshabilitado para este rol.")

        st.divider()
        if puede_cambiar_estado:
            abrir_gestion_receta = st.checkbox(
                "Mostrar gestion medica: suspender o editar una indicacion activa",
                value=False,
                key=f"abrir_gestion_receta_{paciente_sel}",
            )
            if abrir_gestion_receta:
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
                                _auditar_recetas(
                                    paciente_sel,
                                    user,
                                    "Indicacion suspendida",
                                    f"{r.get('med', '')} | Motivo: {motivo_cambio.strip()}",
                                    referencia=r.get("med", "")[:80],
                                    criticidad="critica",
                                    extra={
                                        "motivo_estado": motivo_cambio.strip(),
                                        "estado_nuevo": "Suspendida",
                                        "origen_registro": r.get("origen_registro", ""),
                                    },
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
                                        "tipo_indicacion": r.get("tipo_indicacion", "Medicacion"),
                                        "solucion": r.get("solucion", ""),
                                        "volumen_ml": r.get("volumen_ml", 0),
                                        "velocidad_ml_h": r.get("velocidad_ml_h"),
                                        "alternar_con": r.get("alternar_con", ""),
                                        "detalle_infusion": r.get("detalle_infusion", ""),
                                        "plan_hidratacion": r.get("plan_hidratacion", []),
                                        "fecha_estado": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                                        "profesional_estado": user["nombre"],
                                        "matricula_estado": user.get("matricula", ""),
                                        "motivo_estado": f"Reemplaza indicacion previa. Motivo: {motivo_cambio.strip()}".strip(),
                                        "origen_registro": "Prescripcion digital",
                                        "empresa": r.get("empresa", mi_empresa),
                                    }
                                )
                                _auditar_recetas(
                                    paciente_sel,
                                    user,
                                    "Indicacion modificada",
                                    f"Anterior: {r.get('med', '')} | Nueva: {nuevo_texto_receta} | Motivo: {motivo_cambio.strip()}",
                                    referencia=nuevo_texto_receta[:80],
                                    criticidad="critica",
                                    extra={
                                        "medicacion_anterior": r.get("med", ""),
                                        "medicacion_nueva": nuevo_texto_receta,
                                        "motivo_estado": motivo_cambio.strip(),
                                        "origen_registro": r.get("origen_registro", ""),
                                    },
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
        abrir_historial_recetas = st.checkbox(
            "Mostrar historial de prescripciones",
            value=False,
            key=f"abrir_historial_recetas_{paciente_sel}",
        )
        if abrir_historial_recetas:
            st.markdown("#### Historial completo")
            limite_hist = seleccionar_limite_registros(
                "Prescripciones a mostrar",
                len(recs_todas),
                key=f"limite_recetas_hist_{paciente_sel}",
                default=30,
            )

            with st.container(height=400):
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
