"""Paneles de panorama, timeline y búsqueda global del historial. Extraído de views/historial.py."""
from collections import Counter
from datetime import timedelta

import pandas as pd
import streamlit as st

from core.utils import ahora, mostrar_dataframe_con_scroll
from views._historial_utils import (
    _actividad_reciente_filas,
    _busqueda_global_resultados,
    _fecha_en_rango_tl,
    _resumen_ejecutivo_secciones,
    _ultimo_evento_global,
)


def render_panorama(secciones, paciente_sel):
    """Métricas globales, gráfico de volumen por módulo y resumen ejecutivo."""
    total_registros = sum(len(v) for v in secciones.values())
    ultimo = _ultimo_evento_global(secciones)

    st.markdown("##### Panorama del paciente")
    m1, m2, m3 = st.columns(3)
    m1.metric("Registros totales", total_registros)
    m2.metric("Secciones con datos", len(secciones))
    m3.metric("Último evento datado", ultimo.strftime("%d/%m/%Y %H:%M") if ultimo else "S/D")

    df_cnt = pd.DataFrame([{"Sección": k, "Cantidad": len(v)} for k, v in sorted(secciones.items(), key=lambda x: -len(x[1]))])
    st.caption("Volumen de registros por módulo")
    _n_mod = len(df_cnt)
    _h_bar = min(280, max(140, 32 * _n_mod + 72))
    st.bar_chart(
        df_cnt.set_index("Sección")["Cantidad"],
        use_container_width=True,
        height=_h_bar,
    )

    df_ej = _resumen_ejecutivo_secciones(secciones)
    if not df_ej.empty:
        with st.expander("Resumen ejecutivo por sección", expanded=False):
            mostrar_dataframe_con_scroll(df_ej, height=min(400, 50 + len(df_ej) * 36))


def render_timeline(secciones, paciente_sel, limite_timeline):
    """Línea de tiempo global con filtro de fechas opcional."""
    with st.expander(" Línea de tiempo global", expanded=True):
        tl_cols = st.columns([1, 1, 1, 1])
        mostrar_tl = tl_cols[0].checkbox(
            "Mostrar timeline",
            value=True,
            key=f"hist_show_tl_{paciente_sel}",
        )
        tl_usar_fecha = tl_cols[1].checkbox(
            "Filtrar por fechas",
            value=False,
            key=f"hist_tl_usa_fecha_{paciente_sel}",
        )
        hoy_tl = ahora().date()
        tl_desde = hoy_tl - timedelta(days=90)
        tl_hasta = hoy_tl
        if tl_usar_fecha:
            rango_tl = st.date_input(
                "Rango de fechas (timeline)",
                value=(tl_desde, hoy_tl),
                key=f"hist_tl_rango_{paciente_sel}",
            )
            if isinstance(rango_tl, tuple) and len(rango_tl) == 2:
                tl_desde, tl_hasta = rango_tl
            elif hasattr(rango_tl, "year"):
                tl_desde = tl_hasta = rango_tl
            if tl_desde > tl_hasta:
                tl_desde, tl_hasta = tl_hasta, tl_desde
        if mostrar_tl:
            filas_tl = _actividad_reciente_filas(secciones, limite_timeline)
            if tl_usar_fecha:
                filas_tl = [
                    f for f in filas_tl
                    if _fecha_en_rango_tl(f["Fecha"], tl_desde, tl_hasta)
                ]
            if filas_tl:
                df_tl = pd.DataFrame(filas_tl)
                altura_tl = min(320, max(180, 36 + len(filas_tl) * 34))
                mostrar_dataframe_con_scroll(df_tl, height=altura_tl)
            else:
                st.caption("No hay registros con fecha reconocible en el rango seleccionado.")


def render_busqueda_global(secciones, paciente_sel):
    """Búsqueda de texto libre en todas las secciones. Devuelve (q_global, hits) para uso del llamador."""
    st.markdown("##### Búsqueda en toda la historia")
    g_cols = st.columns([2, 1])
    with g_cols[0]:
        q_global = st.text_input(
            "Texto en todas las secciones",
            "",
            key=f"hist_global_q_{paciente_sel}",
            placeholder="Apellido, medicación, tipo de estudio, profesional…",
        )
    with g_cols[1]:
        max_hits = st.selectbox("Máx. resultados", [20, 40, 80], index=0, key=f"hist_global_max_{paciente_sel}")

    if q_global.strip():
        hits = _busqueda_global_resultados(secciones, q_global.strip(), max_hits)
        if not hits:
            st.caption("No hay coincidencias en ninguna sección.")
        else:
            conteo_sec = Counter(h["seccion"] for h in hits)
            top_sec, top_n = conteo_sec.most_common(1)[0]
            st.success(
                f"**{len(hits)}** coincidencia(s) en **{len(conteo_sec)}** sección(es). "
                f"Mayor densidad: **{top_sec}** ({top_n})."
            )
            if len(conteo_sec) > 1:
                df_dist = (
                    pd.DataFrame(conteo_sec.most_common(), columns=["Sección", "Coincidencias"])
                    .sort_values("Coincidencias", ascending=False)
                    .set_index("Sección")
                )
                st.caption("Coincidencias por módulo")
                st.bar_chart(df_dist, use_container_width=True, height=min(220, 40 + len(conteo_sec) * 28))

            df_h = pd.DataFrame(hits).rename(
                columns={"seccion": "Sección", "fecha": "Fecha", "resumen": "Resumen"}
            )
            altura_h = min(280, max(168, 36 + len(hits) * 32))
            mostrar_dataframe_con_scroll(df_h, height=altura_h)
            st.caption(
                f"Tip: usá «Abrir sección» para ir a **{top_sec}** (más resultados) o elegí otra fila en el selector."
            )
            etiquetas = [f"{i + 1}. {h['seccion']} — {h['fecha']}" for i, h in enumerate(hits)]
            sel_hit = st.selectbox(
                "Ir a sección del resultado",
                etiquetas,
                key=f"hist_global_pick_{paciente_sel}",
            )
            if st.button("Abrir sección y filtrar con esta búsqueda", key=f"hist_global_go_{paciente_sel}", type="primary"):
                idx_hit = etiquetas.index(sel_hit)
                destino = hits[idx_hit]["seccion"]
                st.session_state[f"hist_seccion_radio_{paciente_sel}"] = destino
                st.session_state[f"hist_buscar_{paciente_sel}_{destino}"] = q_global.strip()
                st.rerun()
    else:
        st.caption("Escribí algo para buscar en toda la historia.")
