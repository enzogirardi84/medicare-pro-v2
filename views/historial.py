import html
from collections import Counter
from datetime import timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio
from core.clinical_exports import (
    build_backup_pdf_bytes,
    build_history_pdf_bytes,
    build_patient_excel_bytes,
    build_patient_json_bytes,
    collect_patient_sections,
)
from core.utils import ahora, mapa_detalles_pacientes, mostrar_dataframe_con_scroll
from features.historial.fechas import registro_en_rango_fechas, sort_registros_por_fecha
from views._historial_utils import (
    LIMITES_REGISTROS,
    SECCIONES_TABLA,
    _actividad_reciente_filas,
    _busqueda_global_resultados,
    _dataframe_seccion_a_csv,
    _fecha_en_rango_tl,
    _nombre_archivo_seguro,
    _registro_coincide_busqueda,
    _resumen_ejecutivo_secciones,
    _ultimo_evento_global,
)
from views._historial_vitales import _render_signos_vitales_con_alertas
from views._historial_render import (
    _render_consentimientos,
    _render_estudios,
    _render_heridas,
    _render_lazy_download,
    _render_registros_genericos,
    _render_seccion_tabla,
)

def render_historial(paciente_sel: str, user=None) -> None:
    if not paciente_sel:
        aviso_sin_paciente()
        return

    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    estado_badge = "[ARCHIVADO DE ALTA]" if detalles.get("estado") == "De Alta" else ""
    nombre_chip = html.escape(paciente_sel.split(" (")[0])
    dni_chip = html.escape(str(detalles.get("dni", "S/D")))
    os_chip = html.escape(str(detalles.get("obra_social", "S/D")))
    tel_chip = html.escape(str(detalles.get("telefono", "S/D")))
    dom = str(detalles.get("direccion", "")).strip()
    dom_chip = html.escape(dom) if dom and dom != "No registrada" else ""

    chips_extra = ""
    if dom_chip:
        chips_extra = f'<span class="mc-chip">Dom.: {dom_chip[:40]}{"…" if len(dom_chip) > 40 else ""}</span>'

    st.markdown(
        f"""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Historia clínica digital {estado_badge}</h2>
            <p class="mc-hero-text">
                Orden sugerido: exportar o respaldar si lo necesitas, revisar el panorama y la linea de tiempo,
                buscar en toda la historia, y al final abrir cada modulo por seccion para el detalle completo.
                En celular, las tablas anchas se pueden desplazar horizontalmente.
            </p>
            <div class="mc-chip-row">
                <span class="mc-chip">{nombre_chip}</span>
                <span class="mc-chip">DNI: {dni_chip}</span>
                <span class="mc-chip">Obra social: {os_chip}</span>
                <span class="mc-chip">Tel: {tel_chip}</span>
                {chips_extra}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    alergias = str(detalles.get("alergias", "")).strip()
    if alergias:
        st.error(f" Alergias: {alergias}")
    patologias = str(detalles.get("patologias", "") or detalles.get("diagnostico", "")).strip()
    if patologias:
        st.warning(f" Antecedentes / diagnóstico: {patologias}")
    diag_ingreso = str(detalles.get("diagnostico_ingreso", "")).strip()
    motivo_ingreso = str(detalles.get("motivo_ingreso", "")).strip()
    if diag_ingreso or motivo_ingreso:
        _txt = " | ".join(filter(None, [diag_ingreso, motivo_ingreso]))
        st.info(f"🏥 Ingreso: **{_txt}**")
    medico_trat = str(detalles.get("medico_tratante", "") or detalles.get("medico", "")).strip()
    if medico_trat:
        st.caption(f" Médico tratante: **{medico_trat}**")

    st.caption(
        "Filtros y límite arriba · exportaciones PDF/Excel/JSON/respaldo · panorama y gráfico · línea de tiempo y búsqueda global · "
        "al final, exploración por sección en franja horizontal (plegable)."
    )

    st.markdown("##### Opciones de visualización")
    col_filt1, col_filt2, col_filt3, col_filt4 = st.columns(4)
    opcion_limite = col_filt1.selectbox("Límite por sección", list(LIMITES_REGISTROS.keys()))
    limite = LIMITES_REGISTROS.get(opcion_limite, 200)
    solo_con_datos = col_filt2.checkbox("Solo secciones con datos", value=True, key=f"hist_solo_datos_{paciente_sel}")
    limite_timeline = col_filt3.selectbox(
        "Eventos en línea de tiempo",
        [15, 25, 40, 60],
        index=1,
        key=f"hist_tl_n_{paciente_sel}",
    )
    col_filt4.info(f"Hasta {limite} ítems al ver una sección.")

    st.markdown("##### Exportación y resguardo")
    r1, r2, r3, r4 = st.columns(4)
    _render_lazy_download(
        r1,
        key_base=f"historial_pdf_{paciente_sel}",
        prepare_label="Preparar historia PDF",
        download_label="Descargar historia PDF",
        build_fn=lambda: build_history_pdf_bytes(st.session_state, paciente_sel, detalles.get("empresa", "")),
        file_name=f"Historia_Clinica_{paciente_sel.replace(' ', '_')}.pdf",
        mime="application/pdf",
    )
    _render_lazy_download(
        r2,
        key_base=f"historial_excel_{paciente_sel}",
        prepare_label="Preparar Excel",
        download_label="Descargar Excel",
        build_fn=lambda: build_patient_excel_bytes(st.session_state, paciente_sel),
        file_name=f"Historia_Clinica_{paciente_sel.replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        unavailable_message="Excel no disponible en este equipo.",
    )
    _render_lazy_download(
        r3,
        key_base=f"historial_respaldo_{paciente_sel}",
        prepare_label="Preparar respaldo PDF",
        download_label="Descargar respaldo PDF",
        build_fn=lambda: build_backup_pdf_bytes(st.session_state, paciente_sel, detalles.get("empresa", "")),
        file_name=f"Respaldo_Clinico_{paciente_sel.replace(' ', '_')}.pdf",
        mime="application/pdf",
    )
    _render_lazy_download(
        r4,
        key_base=f"historial_json_{paciente_sel}",
        prepare_label="Preparar JSON",
        download_label="Descargar JSON",
        build_fn=lambda: build_patient_json_bytes(st.session_state, paciente_sel),
        file_name=f"Historia_Clinica_{paciente_sel.replace(' ', '_')}.json",
        mime="application/json",
    )

    st.divider()
    st.markdown(
        """
        <div class="mc-grid-3">
            <div class="mc-card"><h4>Respaldo y filtros</h4><p>PDF, Excel, JSON o respaldo antes de profundizar; limite por seccion y solo modulos con datos.</p></div>
            <div class="mc-card"><h4>Panorama y linea de tiempo</h4><p>Volumen por modulo y mezcla cronologica de eventos con fecha reconocible.</p></div>
            <div class="mc-card"><h4>Busqueda y detalle</h4><p>Texto en toda la historia y luego cada seccion en tabla o ficha segun el tipo de registro.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    secciones = collect_patient_sections(st.session_state, paciente_sel)
    if not any(secciones.values()):
        bloque_estado_vacio(
            "Historia sin registros",
            "No se encontraron registros clínicos agregados para este paciente.",
            sugerencia="Los datos aparecen cuando se usan Clínica, Recetas, Evolución y el resto de módulos.",
        )
        return

    if solo_con_datos:
        secciones = {k: v for k, v in secciones.items() if v}

    if not secciones:
        bloque_estado_vacio(
            "Filtro demasiado estricto",
            "No quedan secciones con datos con el filtro «solo secciones con datos».",
            sugerencia="Desactivá el filtro o registrá información en otros módulos primero.",
        )
        return

    st.caption(
        "Panel con desplazamiento vertical: panorámica, búsqueda global y detalle por sección (scroll interno)."
    )
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

    st.divider()
    lista_secciones = list(secciones.keys())
    key_sec = f"hist_seccion_radio_{paciente_sel}"
    if key_sec not in st.session_state:
        st.session_state[key_sec] = lista_secciones[0]
    else:
        _prev = st.session_state[key_sec]
        if _prev not in lista_secciones:
            st.session_state[key_sec] = lista_secciones[0]

    with st.expander(" Explorar por sección", expanded=True):
        st.caption(
            "Franja horizontal: en el celular deslizá con el dedo; en PC usá la rueda o la barra inferior. "
            "Podés plegar este bloque para ganar espacio."
        )
        st.markdown(
            '<div class="mc-hist-cortina-mark" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
        seccion_actual = st.pills(
            "Elegí una sección",
            lista_secciones,
            selection_mode="single",
            key=key_sec,
            label_visibility="collapsed",
        )
    if not seccion_actual:
        seccion_actual = st.session_state.get(key_sec) or lista_secciones[0]
    registros = secciones.get(seccion_actual, [])

    if not registros:
        bloque_estado_vacio(
            "Sección vacía",
            "Esta sección no tiene filas para mostrar.",
            sugerencia="Elegí otra sección en el listado o verificá que existan cargas en ese módulo.",
        )
        return

    c_opt1, c_opt2, c_opt3 = st.columns(3)
    usar_fecha = c_opt1.checkbox(
        "Filtrar esta sección por fechas de los registros",
        value=False,
        key=f"hist_use_fecha_{paciente_sel}",
    )
    incluir_sin_fecha = c_opt2.checkbox(
        "Incluir registros sin fecha (si el filtro está activo)",
        value=True,
        key=f"hist_sin_fecha_{paciente_sel}",
    )
    orden_etiqueta = c_opt3.radio(
        "Orden",
        ["Más recientes primero", "Más antiguos primero"],
        horizontal=True,
        key=f"hist_orden_{paciente_sel}",
    )
    recientes_primero = orden_etiqueta.startswith("Más recientes")

    hoy = ahora().date()
    default_desde = hoy - timedelta(days=90)
    if usar_fecha:
        rango = st.date_input(
            "Rango (fecha del registro)",
            value=(default_desde, hoy),
            key=f"hist_rango_fecha_{paciente_sel}_{seccion_actual}",
        )
        if isinstance(rango, tuple) and len(rango) == 2:
            d_desde, d_hasta = rango[0], rango[1]
        elif hasattr(rango, "year"):
            d_desde = d_hasta = rango
        else:
            d_desde, d_hasta = default_desde, hoy
        if d_desde > d_hasta:
            d_desde, d_hasta = d_hasta, d_desde
        registros_fecha = [
            r
            for r in registros
            if registro_en_rango_fechas(
                r, d_desde, d_hasta, incluir_sin_fecha=incluir_sin_fecha
            )
        ]
    else:
        registros_fecha = list(registros)

    buscar = st.text_input(
        "Buscar texto en esta sección",
        "",
        key=f"hist_buscar_{paciente_sel}_{seccion_actual}",
        placeholder="Profesional, medicación, detalle, estado…",
    )
    registros_filtrados = [r for r in registros_fecha if _registro_coincide_busqueda(r, buscar)]
    if buscar.strip() and not registros_filtrados:
        bloque_estado_vacio(
            "Sin coincidencias",
            "Ningún registro de esta sección coincide con el texto buscado.",
            sugerencia="Probá otras palabras o limpiá el campo de búsqueda.",
        )
        return

    registros_base = registros_filtrados if buscar.strip() else registros_fecha
    if usar_fecha and not registros_base:
        bloque_estado_vacio(
            "Fuera de rango",
            "Ningún registro cae en el rango de fechas indicado.",
            sugerencia="Ampliá las fechas o activá «Incluir registros sin fecha» si corresponde.",
        )
        return

    registros_ordenados = sort_registros_por_fecha(
        registros_base, recientes_primero=recientes_primero
    )
    total_registros_seccion = len(registros_ordenados)
    limite_pagina = min(max(int(limite), 1), 500)
    paginas = max((total_registros_seccion - 1) // limite_pagina + 1, 1)
    col_pag1, col_pag2 = st.columns([2, 1])
    col_pag1.caption(f"Tamaño de página: {limite_pagina} registro(s)")
    pagina = col_pag2.number_input(
        "Página de la sección",
        min_value=1,
        max_value=paginas,
        value=1,
        step=1,
        key=f"hist_pag_{paciente_sel}_{_nombre_archivo_seguro(seccion_actual, 24)}",
    )
    inicio = (int(pagina) - 1) * limite_pagina
    fin = inicio + limite_pagina
    registros_mostrar = registros_ordenados[inicio:fin]

    st.caption(
        f"Mostrando {len(registros_mostrar)} de {len(registros_base)} registros en «{seccion_actual}»"
        f" (página {int(pagina)}/{paginas})"
        f"{f' (filtrados de {len(registros)})' if (buscar.strip() or usar_fecha) else ''}."
    )

    csv_bytes = _dataframe_seccion_a_csv(registros_mostrar)
    if csv_bytes:
        fn = f"Historia_{_nombre_archivo_seguro(paciente_sel.split('(')[0])}_{_nombre_archivo_seguro(seccion_actual, 40)}.csv"
        st.download_button(
            "Descargar esta vista en CSV",
            csv_bytes,
            file_name=fn,
            mime="text/csv; charset=utf-8",
            key=f"hist_csv_vista_{paciente_sel}_{_nombre_archivo_seguro(seccion_actual, 30)}",
        )

    if seccion_actual == "Signos Vitales":
        _render_signos_vitales_con_alertas(registros_mostrar, paciente_sel)
    elif seccion_actual in SECCIONES_TABLA:
        _render_seccion_tabla(registros_mostrar, seccion_actual)
    elif seccion_actual == "Consentimientos":
        _render_consentimientos(registros_mostrar, paciente_sel)
    elif seccion_actual == "Estudios Complementarios":
        _render_estudios(registros_mostrar, paciente_sel)
    elif seccion_actual == "Registro de Heridas":
        _render_heridas(registros_mostrar, paciente_sel)
    else:
        _render_registros_genericos(registros_mostrar, seccion_actual, paciente_sel)
