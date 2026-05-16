import html
from datetime import timedelta

import streamlit as st

from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio
from core.clinical_exports import (
    build_backup_pdf_bytes,
    build_history_pdf_bytes,
    build_patient_excel_bytes,
    build_patient_json_bytes,
    collect_patient_sections,
)
from core.utils import ahora, mapa_detalles_pacientes
from features.historial.fechas import registro_en_rango_fechas, sort_registros_por_fecha
from views._historial_utils import (
    LIMITES_REGISTROS,
    SECCIONES_TABLA,
    _dataframe_seccion_a_csv,
    _nombre_archivo_seguro,
    _registro_coincide_busqueda,
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
from views._historial_paneles import (
    render_resumen_clinico,
    render_panorama,
    render_tarjetas_secciones,
    render_timeline,
    render_busqueda_global,
)

@st.cache_data(ttl=120)
def _cached_collect_patient_sections(paciente_sel: str):
    """Cache de secciones del paciente para acelerar transiciones entre módulos."""
    return collect_patient_sections(st.session_state, paciente_sel)

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

    secciones_base = _cached_collect_patient_sections(paciente_sel)
    secciones_con_datos_base = {nombre: registros for nombre, registros in secciones_base.items() if registros}
    total_registros_base = sum(len(registros) for registros in secciones_base.values())
    ultimo_base = _ultimo_evento_global(secciones_base)

    # ── Filtros globales compactos ───────────────────────────────────────
    col_filt1, col_filt2, col_filt3, col_filt4 = st.columns([1.2, 1.2, 1, 1])
    opcion_limite = col_filt1.selectbox("Limite por seccion", list(LIMITES_REGISTROS.keys()), label_visibility="collapsed")
    limite = LIMITES_REGISTROS.get(opcion_limite, 200)
    solo_con_datos = col_filt2.checkbox("Solo secciones con datos", value=True, key=f"hist_solo_datos_{paciente_sel}")
    limite_timeline = col_filt3.selectbox(
        "Eventos timeline",
        [15, 25, 40, 60],
        index=1,
        key=f"hist_tl_n_{paciente_sel}",
        label_visibility="collapsed",
    )
    col_filt4.caption(f"Hasta {limite} items por seccion.")

    secciones = dict(secciones_base)
    if solo_con_datos:
        secciones = {k: v for k, v in secciones.items() if v}

    if not secciones_con_datos_base:
        tab_r, tab_t, tab_b, tab_s = st.tabs(["Resumen", "Linea de Tiempo", "Busqueda", "Secciones"])
        with tab_r:
            bloque_estado_vacio(
                "Historia sin registros",
                "No se encontraron registros clinicos agregados para este paciente.",
                sugerencia="Los datos aparecen cuando se usan Clinica, Recetas, Evolucion y el resto de modulos.",
            )
        return

    tab_r, tab_t, tab_b, tab_s = st.tabs([
        "Resumen y exportaciones",
        "Linea de Tiempo",
        "Busqueda global",
        "Secciones",
    ])

    # ── TAB 1: RESUMEN ───────────────────────────────────────────────────
    with tab_r:
        render_resumen_clinico(paciente_sel, detalles, secciones_base, total_registros_base, ultimo_base)
        st.markdown("##### Exportar historia clinica")
        r1, r2, r3, r4 = st.columns([1.35, 1.0, 1.0, 0.95])
        _render_lazy_download(
            r1,
            key_base=f"historial_pdf_{paciente_sel}",
            prepare_label="Preparar PDF clinico",
            download_label="Descargar PDF clinico",
            build_fn=lambda: build_history_pdf_bytes(st.session_state, paciente_sel, detalles.get("empresa", "")),
            file_name=f"Historia_Clinica_{paciente_sel.replace(' ', '_')}.pdf",
            mime="application/pdf",
            unavailable_message="No se pudo generar el PDF clinico. Verifica ReportLab y los datos cargados.",
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
        render_panorama(secciones, paciente_sel)
        render_tarjetas_secciones(secciones_con_datos_base, paciente_sel)

    # ── TAB 2: LINEA DE TIEMPO ──────────────────────────────────────────
    with tab_t:
        render_timeline(secciones, paciente_sel, limite_timeline)

    # ── TAB 3: BUSQUEDA GLOBAL ──────────────────────────────────────────
    with tab_b:
        render_busqueda_global(secciones, paciente_sel)

    # ── TAB 4: SECCIONES ────────────────────────────────────────────────
    with tab_s:
        lista_secciones = list(secciones.keys())
        key_sec = f"hist_seccion_radio_{paciente_sel}"
        if key_sec not in st.session_state:
            st.session_state[key_sec] = lista_secciones[0]
        else:
            _prev = st.session_state[key_sec]
            if _prev not in lista_secciones:
                st.session_state[key_sec] = lista_secciones[0]

        seccion_actual = st.pills(
            "Elegir seccion",
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
                "Seccion vacia",
                "Esta seccion no tiene filas para mostrar.",
                sugerencia="Elegi otra seccion en el listado o verifica que existan cargas en ese modulo.",
            )
            return

        with st.expander("Filtros de la seccion", expanded=False):
            col_f1, col_f2, col_f3 = st.columns(3)
            usar_fecha = col_f1.checkbox(
                "Filtrar por fechas",
                value=False,
                key=f"hist_use_fecha_{paciente_sel}",
            )
            incluir_sin_fecha = col_f2.checkbox(
                "Incluir sin fecha",
                value=True,
                key=f"hist_sin_fecha_{paciente_sel}",
            )
            orden_etiqueta = col_f3.radio(
                "Orden",
                ["Mas recientes", "Mas antiguos"],
                horizontal=True,
                key=f"hist_orden_{paciente_sel}",
            )
            recientes_primero = orden_etiqueta.startswith("Mas recientes")

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
                    r for r in registros
                    if registro_en_rango_fechas(r, d_desde, d_hasta, incluir_sin_fecha=incluir_sin_fecha)
                ]
            else:
                registros_fecha = list(registros)

            buscar = st.text_input(
                "Buscar en esta seccion",
                "",
                key=f"hist_buscar_{paciente_sel}_{seccion_actual}",
                placeholder="Profesional, medicacion, detalle, estado...",
            )

        registros_filtrados = [r for r in registros_fecha if _registro_coincide_busqueda(r, buscar)]
        if buscar.strip() and not registros_filtrados:
            bloque_estado_vacio(
                "Sin coincidencias",
                "Ningun registro coincide con el texto buscado.",
                sugerencia="Proba otras palabras o limpia el campo de busqueda.",
            )
            return

        registros_base_sec = registros_filtrados if buscar.strip() else registros_fecha
        if usar_fecha and not registros_base_sec:
            bloque_estado_vacio(
                "Fuera de rango",
                "Ningun registro cae en el rango de fechas indicado.",
                sugerencia="Amplia las fechas o activa Incluir registros sin fecha si corresponde.",
            )
            return

        registros_ordenados = sort_registros_por_fecha(registros_base_sec, recientes_primero=recientes_primero)
        total_registros_seccion = len(registros_ordenados)
        limite_pagina = min(max(int(limite), 1), 500)
        paginas = max((total_registros_seccion - 1) // limite_pagina + 1, 1)
        col_pag1, col_pag2 = st.columns([2, 1])
        col_pag1.caption(f"Pagina: {limite_pagina} registro(s)")
        pagina = col_pag2.number_input(
            "Pagina",
            min_value=1,
            max_value=paginas,
            value=1,
            step=1,
            label_visibility="collapsed",
            key=f"hist_pag_{paciente_sel}_{_nombre_archivo_seguro(seccion_actual, 24)}",
        )
        inicio = (int(pagina) - 1) * limite_pagina
        fin = inicio + limite_pagina
        registros_mostrar = registros_ordenados[inicio:fin]

        st.caption(
            f"Mostrando {len(registros_mostrar)} de {len(registros_base_sec)} registros en {seccion_actual}"
            f" (pagina {int(pagina)}/{paginas})"
            f"{f' (filtrados de {len(registros)})' if (buscar.strip() or usar_fecha) else ''}."
        )

        csv_bytes = _dataframe_seccion_a_csv(registros_mostrar)
        if csv_bytes:
            fn = f"Historia_{_nombre_archivo_seguro(paciente_sel.split('(')[0])}_{_nombre_archivo_seguro(seccion_actual, 40)}.csv"
            st.download_button(
                "Descargar vista en CSV",
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
