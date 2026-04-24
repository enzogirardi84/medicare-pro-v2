"""Paneles de resumen, panorama, timeline y busqueda global del historial."""

import html
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from core.utils import ahora, mostrar_dataframe_con_scroll
from features.historial.fechas import parse_registro_fecha_hora
from views._historial_utils import (
    _actividad_reciente_filas,
    _busqueda_global_resultados,
    _fecha_en_rango_tl,
    _resumen_ejecutivo_secciones,
    _resumen_linea_tiempo,
    _ultimo_evento_global,
)


def _primer_valor(*valores: Any) -> str:
    for valor in valores:
        if valor in (None, ""):
            continue
        texto = str(valor).strip()
        if texto:
            return texto
    return "S/D"


def _edad_desde_fnac(valor: Any) -> str:
    dt = parse_registro_fecha_hora({"fecha": str(valor or "")})
    if not dt:
        return ""
    hoy = ahora().date()
    edad = hoy.year - dt.date().year - ((hoy.month, hoy.day) < (dt.date().month, dt.date().day))
    return f"{edad} anos" if edad >= 0 else ""


def _ultimo_registro(registros: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not registros:
        return None
    mejor: Optional[Dict[str, Any]] = None
    mejor_dt: Optional[datetime] = None
    for registro in registros:
        dt = parse_registro_fecha_hora(registro)
        if dt and (mejor_dt is None or dt > mejor_dt):
            mejor_dt = dt
            mejor = registro
    return mejor or (registros[-1] if registros else {})


def _fecha_registro_legible(registro: Optional[Dict[str, Any]]) -> str:
    if not registro:
        return "S/D"
    dt = parse_registro_fecha_hora(registro)
    if dt:
        return dt.strftime("%d/%m/%Y %H:%M")
    return _primer_valor(
        registro.get("fecha_hora_programada"),
        registro.get("fecha_hora"),
        registro.get("fecha"),
        registro.get("fecha_programada"),
        registro.get("creado_en"),
        registro.get("fecha_evento"),
    )


def _ultimo_movimiento_con_seccion(
    secciones: Dict[str, List[Dict[str, Any]]],
) -> Tuple[str, Optional[Dict[str, Any]], Optional[datetime]]:
    mejor_seccion = "Sin actividad"
    mejor_registro: Optional[Dict[str, Any]] = None
    mejor_dt: Optional[datetime] = None
    for seccion, registros in secciones.items():
        for registro in registros:
            dt = parse_registro_fecha_hora(registro)
            if dt and (mejor_dt is None or dt > mejor_dt):
                mejor_dt = dt
                mejor_registro = registro
                mejor_seccion = seccion
    if mejor_registro is not None:
        return mejor_seccion, mejor_registro, mejor_dt
    for seccion, registros in secciones.items():
        if registros:
            return seccion, registros[-1], None
    return mejor_seccion, None, None


def _medicaciones_activas(registros: List[Dict[str, Any]]) -> int:
    activas = 0
    for registro in registros:
        estado = str(
            registro.get("estado_receta", registro.get("estado_clinico", "Activa")) or ""
        ).strip().lower()
        if estado in {"suspendida", "suspendido", "modificada", "modificado", "finalizada", "finalizado"}:
            continue
        activas += 1
    return activas


def render_resumen_clinico(
    paciente_sel: str,
    detalles: Dict[str, Any],
    secciones: Dict[str, List[Dict[str, Any]]],
    total_registros: int,
    ultimo_evento: Optional[datetime],
) -> None:
    nombre_visible = html.escape(paciente_sel.split(" (")[0])
    edad = _edad_desde_fnac(detalles.get("fnac"))
    estado = _primer_valor(detalles.get("estado"), "Activo")
    empresa = html.escape(_primer_valor(detalles.get("empresa"), "Sin empresa"))

    seccion_ult, registro_ult, dt_ult = _ultimo_movimiento_con_seccion(secciones)
    resumen_ult = (
        _resumen_linea_tiempo(seccion_ult, registro_ult or {})
        if registro_ult
        else "Todavia no hay actividad registrada."
    )
    fecha_ult = dt_ult.strftime("%d/%m/%Y %H:%M") if dt_ult else _fecha_registro_legible(registro_ult)

    vital_ult = _ultimo_registro(secciones.get("Signos Vitales", []))
    vital_titulo = "Sin controles"
    vital_copy = "No hay signos vitales cargados todavia."
    if vital_ult:
        vital_titulo = _primer_valor(vital_ult.get("TA"), vital_ult.get("FC"), vital_ult.get("Sat"), "Control cargado")
        vital_copy = f"{_resumen_linea_tiempo('Signos Vitales', vital_ult)} | {_fecha_registro_legible(vital_ult)}"

    plan_regs = secciones.get("Plan Terapeutico", [])
    plan_ult = _ultimo_registro(plan_regs)
    plan_titulo = f"{_medicaciones_activas(plan_regs)} activas"
    plan_copy = "Sin indicaciones cargadas."
    if plan_ult:
        plan_copy = (
            f"{_primer_valor(plan_ult.get('med'), plan_ult.get('detalle'), 'Ultima indicacion registrada')} | "
            f"{_fecha_registro_legible(plan_ult)}"
        )

    st.markdown(
        f"""
        <div class="mc-module-shell">
            <div class="mc-module-shell-head">
                <div class="mc-module-shell-kicker">Resumen clinico rapido</div>
                <h3 class="mc-module-shell-title">Historia completa de {nombre_visible}</h3>
                <p class="mc-module-shell-copy">
                    PDF clinico listo para archivo, panorama del paciente y detalle por modulo en una sola vista.
                    Empresa: {empresa}.
                </p>
            </div>
            <div class="mc-module-shell-grid">
                <div class="mc-module-feature">
                    <span class="mc-module-feature-kicker">Ultimo movimiento</span>
                    <div class="mc-module-feature-title">{html.escape(f"{seccion_ult} | {fecha_ult}")}</div>
                    <div class="mc-module-feature-copy">{html.escape(resumen_ult[:180])}</div>
                </div>
                <div class="mc-module-stat">
                    <span class="mc-module-stat-label">Signos vitales</span>
                    <div class="mc-module-stat-value">{html.escape(vital_titulo[:36])}</div>
                    <div class="mc-module-feature-copy">{html.escape(vital_copy[:180])}</div>
                </div>
                <div class="mc-module-stat">
                    <span class="mc-module-stat-label">Plan terapeutico</span>
                    <div class="mc-module-stat-value">{html.escape(plan_titulo)}</div>
                    <div class="mc-module-feature-copy">{html.escape(plan_copy[:180])}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    ficha = [
        f"Estado: {estado}",
        f"Edad: {edad}" if edad else "",
        f"Registros: {total_registros}",
        f"Ultimo evento: {ultimo_evento.strftime('%d/%m/%Y %H:%M')}" if ultimo_evento else "Ultimo evento: S/D",
    ]
    if detalles.get("alergias"):
        ficha.append(f"Alergias: {detalles.get('alergias')}")
    if detalles.get("patologias"):
        ficha.append(f"Antecedentes: {detalles.get('patologias')}")
    ficha_txt = " | ".join(html.escape(str(item)) for item in ficha if item)
    st.markdown(f'<div class="mc-callout"><strong>Ficha rapida:</strong> {ficha_txt}</div>', unsafe_allow_html=True)


def render_panorama(secciones, paciente_sel):
    """Metricas globales, grafico por modulo y resumen ejecutivo."""
    total_registros = sum(len(v) for v in secciones.values())
    ultimo = _ultimo_evento_global(secciones)

    st.markdown("##### Panorama del paciente")
    m1, m2, m3 = st.columns(3)
    m1.metric("Registros totales", total_registros)
    m2.metric("Secciones con datos", len(secciones))
    m3.metric("Ultimo evento datado", ultimo.strftime("%d/%m/%Y %H:%M") if ultimo else "S/D")

    df_cnt = pd.DataFrame(
        [{"Seccion": k, "Cantidad": len(v)} for k, v in sorted(secciones.items(), key=lambda x: -len(x[1]))]
    )
    st.caption("Volumen de registros por modulo")
    altura = min(280, max(140, 32 * len(df_cnt) + 72))
    st.bar_chart(
        df_cnt.set_index("Seccion")["Cantidad"],
        use_container_width=True,
        height=altura,
    )

    df_ej = _resumen_ejecutivo_secciones(secciones)
    if not df_ej.empty:
        with st.expander("Resumen ejecutivo por seccion", expanded=False):
            mostrar_dataframe_con_scroll(df_ej, height=min(400, 50 + len(df_ej) * 36))


def render_tarjetas_secciones(
    secciones: Dict[str, List[Dict[str, Any]]],
    paciente_sel: str,
    max_tarjetas: int = 6,
) -> None:
    top = sorted(
        ((nombre, registros) for nombre, registros in secciones.items() if registros),
        key=lambda item: len(item[1]),
        reverse=True,
    )
    if not top:
        return

    st.markdown("##### Modulos con mas actividad")
    columnas = st.columns(3)
    for idx, (seccion, registros) in enumerate(top[:max_tarjetas]):
        ultimo = _ultimo_registro(registros)
        resumen = _resumen_linea_tiempo(seccion, ultimo or {})
        fecha = _fecha_registro_legible(ultimo)
        with columnas[idx % 3]:
            st.markdown(
                f"""
                <div class="mc-card">
                    <h4>{html.escape(seccion)}</h4>
                    <p>{len(registros)} registros cargados.</p>
                    <p>Ultimo movimiento: {html.escape(fecha)}</p>
                    <p>{html.escape(resumen[:150])}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Abrir modulo", key=f"hist_open_card_{paciente_sel}_{idx}", use_container_width=True):
                st.session_state[f"hist_seccion_radio_{paciente_sel}"] = seccion
                st.rerun()

    if len(top) > max_tarjetas:
        st.caption(f"Se muestran {max_tarjetas} modulos prioritarios de {len(top)} con actividad.")


def render_timeline(secciones, paciente_sel, limite_timeline):
    """Linea de tiempo global con filtro opcional de fechas."""
    with st.expander(" Linea de tiempo global", expanded=True):
        columnas = st.columns([1, 1, 1, 1])
        mostrar_tl = columnas[0].checkbox(
            "Mostrar timeline",
            value=True,
            key=f"hist_show_tl_{paciente_sel}",
        )
        usar_fecha = columnas[1].checkbox(
            "Filtrar por fechas",
            value=False,
            key=f"hist_tl_usa_fecha_{paciente_sel}",
        )
        hoy = ahora().date()
        fecha_desde = hoy - timedelta(days=90)
        fecha_hasta = hoy
        if usar_fecha:
            rango = st.date_input(
                "Rango de fechas (timeline)",
                value=(fecha_desde, hoy),
                key=f"hist_tl_rango_{paciente_sel}",
            )
            if isinstance(rango, tuple) and len(rango) == 2:
                fecha_desde, fecha_hasta = rango
            elif hasattr(rango, "year"):
                fecha_desde = fecha_hasta = rango
            if fecha_desde > fecha_hasta:
                fecha_desde, fecha_hasta = fecha_hasta, fecha_desde
        if mostrar_tl:
            filas_tl = _actividad_reciente_filas(secciones, limite_timeline)
            if usar_fecha:
                filas_tl = [
                    fila for fila in filas_tl if _fecha_en_rango_tl(fila["Fecha"], fecha_desde, fecha_hasta)
                ]
            if filas_tl:
                df_tl = pd.DataFrame(filas_tl)
                altura = min(320, max(180, 36 + len(filas_tl) * 34))
                mostrar_dataframe_con_scroll(df_tl, height=altura)
            else:
                st.caption("No hay registros con fecha reconocible en el rango seleccionado.")


def render_busqueda_global(secciones, paciente_sel):
    """Busqueda de texto libre en todas las secciones."""
    st.markdown("##### Busqueda en toda la historia")
    g_cols = st.columns([2, 1])
    with g_cols[0]:
        q_global = st.text_input(
            "Texto en todas las secciones",
            "",
            key=f"hist_global_q_{paciente_sel}",
            placeholder="Apellido, medicacion, tipo de estudio, profesional...",
        )
    with g_cols[1]:
        max_hits = st.selectbox("Max. resultados", [20, 40, 80], index=0, key=f"hist_global_max_{paciente_sel}")

    if q_global.strip():
        hits = _busqueda_global_resultados(secciones, q_global.strip(), max_hits)
        if not hits:
            st.caption("No hay coincidencias en ninguna seccion.")
        else:
            conteo_sec = Counter(hit["seccion"] for hit in hits)
            top_sec, top_n = conteo_sec.most_common(1)[0]
            st.success(
                f"**{len(hits)}** coincidencia(s) en **{len(conteo_sec)}** seccion(es). "
                f"Mayor densidad: **{top_sec}** ({top_n})."
            )
            if len(conteo_sec) > 1:
                df_dist = (
                    pd.DataFrame(conteo_sec.most_common(), columns=["Seccion", "Coincidencias"])
                    .sort_values("Coincidencias", ascending=False)
                    .set_index("Seccion")
                )
                st.caption("Coincidencias por modulo")
                st.bar_chart(df_dist, use_container_width=True, height=min(220, 40 + len(conteo_sec) * 28))

            df_hits = pd.DataFrame(hits).rename(
                columns={"seccion": "Seccion", "fecha": "Fecha", "resumen": "Resumen"}
            )
            altura = min(280, max(168, 36 + len(hits) * 32))
            mostrar_dataframe_con_scroll(df_hits, height=altura)
            st.caption(
                f"Tip: usa 'Abrir seccion' para ir a **{top_sec}** (mas resultados) o elige otra fila en el selector."
            )
            etiquetas = [f"{idx + 1}. {hit['seccion']} - {hit['fecha']}" for idx, hit in enumerate(hits)]
            sel_hit = st.selectbox(
                "Ir a seccion del resultado",
                etiquetas,
                key=f"hist_global_pick_{paciente_sel}",
            )
            if st.button("Abrir seccion y filtrar con esta busqueda", key=f"hist_global_go_{paciente_sel}", type="primary"):
                idx_hit = etiquetas.index(sel_hit)
                destino = hits[idx_hit]["seccion"]
                st.session_state[f"hist_seccion_radio_{paciente_sel}"] = destino
                st.session_state[f"hist_buscar_{paciente_sel}_{destino}"] = q_global.strip()
                st.rerun()
    else:
        st.caption("Escribi algo para buscar en toda la historia.")
